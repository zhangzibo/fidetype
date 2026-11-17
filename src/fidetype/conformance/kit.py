"""The NTS conformance kit (roadmap P7-01).

A small set of example files, one or more per wire form of NTS 1.0 RC4:
JSON Lines input streams (dense and sparse frames, ``meta`` conventions,
events), NPZ, decision logs (text, intent, control), the LSL binding
(``nts-lsl/0.1``) and the WebSocket binding (``nts-ws/0.1``). Each file has
an expected verdict (``accept``, ``accept-with-warnings`` or ``reject``),
the rule ids that it exercises and the checks that must fail or warn.

The kit does not replace the golden vectors (``spec/conformance/<profile>/``,
345 files). The vectors test every edge of every rule. The kit is the short
list that a new implementer runs first: realistic files, one verdict each.

Layout (``spec/conformance/kit/``)::

    kit.json                 index of all entries (schema fidetype.conformance.kit/1)
    rule-map.json            check id -> rule ids (from spec Appendix C.1)
    <profile>/manifest.json  the entries of one suite profile, in the vector manifest
                             format, so the SDK runners use them as they are:
                             fidetype-ts conformance --vectors spec/conformance/kit
                             fidetype-rs conformance --vectors spec/conformance/kit
    <profile>/kNN-*.{jsonl,npz,json}

Regenerate with ``nts-conform build --out spec/conformance/kit``. All content
is synthetic and written by hand or from fixed numbers. No data from people.
Licence: Apache-2.0, as the repository.

Binary protobuf is not a wire form in RC4: the proto files define the data
model and the JSON mapping, and the binary framing is roadmap P1-05. The
JSON Lines files of the kit are the JSON mapping.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from os import PathLike
from pathlib import Path
from typing import Any, Callable

import numpy as np

from fidetype.conformance.vectors import MANIFEST_SCHEMA

KIT_SCHEMA = "fidetype.conformance.kit/1"
KIT_VERSION = "0.2.0"  # 0.2.0 (P7-02, P1-16): K32-K36, stream_level, SDK-checked warnings and levels
VERDICTS = ("accept", "accept-with-warnings", "reject")
#: The stream levels of spec 9.2, low to high. "stream_level" of a kit entry is the highest one that it reaches.
STREAM_LEVELS = ("core", "trust-ready", "provenance")
#: Wire forms that have a stream level (spec 9.2 judges input streams, not decision logs or captures).
LEVELLED_FORMS = ("jsonl-stream", "npz")
WIRE_FORMS = {
    "jsonl-stream": "JSON Lines input stream (8.1.1): header, frames, events",
    "npz": "NPZ frame core (8.1.2)",
    "jsonl-decision-log": "JSON Lines decision log (6, 7.3.5, 7.4.5): trust_decision lines, no header",
    "lsl-capture": "LSL binding nts-lsl/0.1 (8.2): stream infos and recorded chunks (scenario JSON)",
    "lsl-decisions-capture": "LSL decisions stream (8.2.6): recorded samples (scenario JSON)",
    "ws-capture": "WebSocket binding nts-ws/0.1 (8.3): recorded /nts messages (scenario JSON)",
    "ws-decisions-capture": "WebSocket /decisions channel (8.3.6): recorded messages (scenario JSON)",
}
HOW_TO_USE = (
    "NTS conformance kit (P7-01). Each entry is one file with an expected verdict. A conforming consumer "
    "accepts the files with expect = accept and rejects the others. A producer-side validator (nts-conform "
    "check) reports no failed check for verdict accept, only the listed warning checks for "
    "accept-with-warnings, and at least the listed failing checks for reject. 'rules' are the NTS 1.0 RC4 "
    "rule ids that the file exercises (spec Appendix C). 'stream_level' (input streams only): the highest stream level "
    "of spec 9.2 that the file reaches (core, trust-ready, provenance); a Trust-ready consumer reports it (spec 9.6). "
    "'warning_checks' lists the advisory checks that warn; they never change the verdict.")

# --- fixed content ----------------------------------------------------------------------------

SV = "1.0"
VOCAB5 = ["<blank>", "a", "b", "c", " "]
FP = 0.04
SHA = "5d41402abc4b2a76b9719d911017c592aaf4d2b2c1f3e5a6978877665544332f"
# Probability rows of a decoder that writes "ab " (blank between the characters).
PROBS = [[0.80, 0.10, 0.04, 0.03, 0.03],
         [0.10, 0.75, 0.05, 0.05, 0.05],
         [0.85, 0.05, 0.04, 0.03, 0.03],
         [0.05, 0.05, 0.80, 0.05, 0.05],
         [0.70, 0.10, 0.10, 0.05, 0.05],
         [0.06, 0.04, 0.04, 0.06, 0.80]]
META = {"device.modality": "emg", "decoder.name": "kit-decoder", "decoder.version": "1.0.0",
        "decoder.causal": True, "decoder.weights_sha256": SHA, "adapter.name": "kit-adapter",
        "adapter.version": "1.0.0", "stream.id": "kit-stream-0001", "calibration.applied": False,
        "data.derived": True, "language": "en"}
CFG_T, CFG_I, CFG_C = "tcfg-0123456789abcdef", "icfg-0123456789abcdef", "ccfg-0123456789abcdef"


def _lp_rows() -> list[list[float]]:
    return [[round(math.log(p), 4) for p in row] for row in PROBS]


def _header(**over: Any) -> dict[str, Any]:
    h: dict[str, Any] = {"type": "header", "spec_version": SV, "vocab": list(VOCAB5), "vocab_type": "char",
                         "blank_id": 0, "source": "kit-decoder", "frame_period": FP, "latency": 0.0,
                         "clock_domain": "trial", "meta": dict(META)}
    h.update(over)
    return h


def _frames(rows: list[list[float]] | None = None) -> list[dict[str, Any]]:
    rows = _lp_rows() if rows is None else rows
    return [{"type": "frame", "t": round(i * FP, 6), "log_probs": r} for i, r in enumerate(rows)]


def _hyp(final: bool = True) -> dict[str, Any]:
    return {"type": "hypothesis", "id": "h1", "is_final": final, "score_semantics": "none",
            "nbest": [{"text": "ab ", "score": -1.1}, {"text": "ab", "score": -2.3}]}


def _lines(objs: list[Any], raw: list[tuple[int, str]] | None = None) -> Callable[[Path], None]:
    """Write JSON Lines. ``raw`` inserts literal lines (index, text) for content that json.dumps cannot make."""
    def w(path: Path) -> None:
        lines = [json.dumps(o, ensure_ascii=False) for o in objs]
        for i, text in raw or []:
            lines.insert(i, text)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    return w


def _json(obj: dict[str, Any]) -> Callable[[Path], None]:
    def w(path: Path) -> None:
        path.write_text(json.dumps(obj, indent=1, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8",
                        newline="\n")

    return w


def _npz_arrays(dtype: Any = np.float32) -> dict[str, np.ndarray]:
    rows = np.array([[math.log(p) for p in r] for r in PROBS], dtype=np.float64)
    return dict(version=np.array(SV), log_probs=rows.astype(dtype),
                frame_times=(np.arange(len(PROBS)) * FP).astype(np.float64), vocab=np.array(VOCAB5, dtype=np.str_),
                vocab_type=np.array("char"), blank_id=np.array(0, dtype=np.int64), source=np.array("kit-decoder"),
                meta_json=np.array(json.dumps(META)), frame_period=np.array(FP, dtype=np.float64),
                latency=np.array(0.0, dtype=np.float64))


def _npz(dtype: Any = np.float32, pickled: bool = False) -> Callable[[Path], None]:
    def w(path: Path) -> None:
        a: dict[str, Any] = _npz_arrays(dtype)
        if pickled:
            a["vocab"] = np.array(list(VOCAB5), dtype=object)
            np.savez(path, **a)  # object arrays are pickled: FIL-1 forbids it
        else:
            np.savez_compressed(path, **a)

    return w


# --- entries ------------------------------------------------------------------------------------


@dataclass
class KitEntry:
    kid: str
    profile: str
    file: str
    wire_form: str
    verdict: str
    rules: list[str]
    description: str
    writer: Callable[[Path], None]
    failing_checks: list[str] = field(default_factory=list)
    warning_checks: list[str] = field(default_factory=list)
    schema_class: str | None = None  # reject entries: why the one-line JSON Schema does (not) see it
    stream_level: str | None = None  # accept entries of LEVELLED_FORMS: highest stream level (default provenance)

    def __post_init__(self) -> None:
        if self.verdict != "reject" and self.wire_form in LEVELLED_FORMS and self.stream_level is None:
            self.stream_level = "provenance"

    @property
    def expect(self) -> str:
        return "reject" if self.verdict == "reject" else "accept"

    @property
    def path(self) -> str:
        return f"{self.profile}/{self.file}"

    def to_manifest(self) -> dict[str, Any]:
        d: dict[str, Any] = {"id": self.kid, "file": self.file, "format": Path(self.file).suffix.lstrip("."),
                             "expect": self.expect, "verdict": self.verdict, "wire_form": self.wire_form,
                             "rules": self.rules, "description": self.description}
        if self.failing_checks:
            d["failing_check"] = self.failing_checks[0]
            d["failing_checks"] = self.failing_checks
        if self.warning_checks:
            d["warning_checks"] = self.warning_checks
        if self.schema_class:
            d["schema_class"] = self.schema_class
        if self.stream_level:
            d["stream_level"] = self.stream_level
        if self.profile == "v0.1" and self.stream_level:
            # The v0.1 consumers of the three SDKs return "warnings" and "level" in their summary (P7-02),
            # so the SDK kit runs check them too (Python = TypeScript = Rust).
            d["expected"] = {"warnings": sorted(self.warning_checks), "level": self.stream_level}
        return d

    def to_index(self) -> dict[str, Any]:
        d = self.to_manifest()
        d = {"id": d.pop("id"), "profile": self.profile, "path": self.path, **d}
        d.pop("file")
        d.pop("failing_check", None)
        d.pop("expected", None)
        return d


def build_kit() -> list[KitEntry]:  # noqa: PLR0915 - one flat list is easier to read
    from fidetype.conformance.profiles import fep0002 as L
    from fidetype.conformance.profiles import fep0004 as W

    ks: list[KitEntry] = []

    def add(*a: Any, **k: Any) -> None:
        ks.append(KitEntry(*a, **k))

    rows = _lp_rows()
    end = {"type": "end"}

    # --- v0.1 suite profile: input streams (JSON Lines, NPZ) ---------------------------------
    add("K01", "v0.1", "k01-text-stream.jsonl", "jsonl-stream", "accept",
        ["HDR-1", "HDR-2", "HDR-4", "HDR-5", "HDR-6", "HDR-7", "HDR-9", "HDR-10", "HDR-11", "FRM-1", "FRM-2", "FRM-3",
         "FRM-4", "FRM-6", "TIM-1", "TIM-2", "SQ-1", "HYP-1", "GEN-2", "GEN-3", "MET-1"],
        "A complete text stream: 1.0 header with provenance meta, six dense frames (one cell -inf as null), "
        "signal_quality, a final hypothesis, end",
        _lines([_header(), *_frames(rows[:2]),
                {"type": "frame", "t": 0.08, "log_probs": [round(math.log(p), 4) for p in (0.88, 0.05, 0.04, 0.03)]
                 + [None]},
                *_frames(rows)[3:], {"type": "signal_quality", "t": 0.2, "value": 0.93, "unit": "index"}, _hyp(), end]))
    sparse = []
    for i, r in enumerate(PROBS):
        top = sorted(range(5), key=lambda j: -r[j])[:2]
        rest = 1.0 - sum(r[j] for j in top)
        sparse.append({"type": "frame", "t": round(i * FP, 6), "top_ids": top,
                       "top_log_probs": [round(math.log(r[j]), 6) for j in top], "rest_log_prob": round(math.log(rest), 6)})
    add("K02", "v0.1", "k02-sparse-frames.jsonl", "jsonl-stream", "accept", ["FRM-2", "FRM-3", "FRM-5", "GEN-3"],
        "Sparse frames: the top two tokens and the rest mass per frame", _lines([_header(), *sparse, end]))
    add("K03", "v0.1", "k03-frames.npz", "npz", "accept", ["FIL-1", "FIL-2", "FRM-1", "FRM-3", "FRM-6", "HDR-2"],
        "The same six frames as NPZ (allow_pickle=False, table dtypes)", _npz())
    add("K04", "v0.1", "k04-npz-float64.npz", "npz", "accept-with-warnings", ["FIL-5"],
        "NPZ with float64 log_probs: a reader accepts any real dtype; the writer SHOULD use float32 (warning)",
        _npz(np.float64), warning_checks=["NTS-NPZ-DTYPE"])
    add("K05", "v0.1", "k05-npz-pickled.npz", "npz", "reject", ["FIL-1"],
        "NPZ whose vocab is a pickled object array: it does not load with allow_pickle=False",
        _npz(pickled=True), failing_checks=["NTS-PARSE"], schema_class="npz")
    add("K06", "v0.1", "k06-header-not-first.jsonl", "jsonl-stream", "reject", ["HDR-1"],
        "A frame comes before the header", _lines([_frames(rows)[0], _header(), *_frames(rows)[1:], end]),
        failing_checks=["NTS-JSONL-HEADER"], schema_class="cross-line")
    bad_len = _frames(rows)
    bad_len[2] = {**bad_len[2], "log_probs": bad_len[2]["log_probs"][:4]}
    add("K07", "v0.1", "k07-short-frame.jsonl", "jsonl-stream", "reject", ["FRM-1"],
        "Frame 3 has four values for a five-token vocab", _lines([_header(), *bad_len, end]),
        failing_checks=["NTS-V-MATCH"], schema_class="cross-line")
    unnorm = _frames(rows)
    unnorm[1] = {**unnorm[1], "log_probs": [-0.1, -0.2, -0.3, -0.4, -0.5]}
    add("K08", "v0.1", "k08-unnormalised-frame.jsonl", "jsonl-stream", "reject", ["FRM-3"],
        "Frame 2 is not normalised (raw scores, not log_softmax output)", _lines([_header(), *unnorm, end]),
        failing_checks=["NTS-NORM"], schema_class="arithmetic")
    add("K09", "v0.1", "k09-nan-token.jsonl", "jsonl-stream", "reject", ["GEN-2"],
        "A frame holds the token NaN: the line is not JSON",
        _lines([_header(), *_frames(rows)[:3], end], raw=[(4, '{"type": "frame", "t": 0.12, "log_probs": '
                                                              '[NaN, -1.0, -2.0, -3.0, -4.0]}')]),
        failing_checks=["NTS-PARSE"], schema_class="parse")
    add("K10", "v0.1", "k10-forward-compatible.jsonl", "jsonl-stream", "accept", ["GEN-4", "MET-3", "HDR-2", "VER-3"],
        "Header 1.3 (a newer minor version) with an unknown header key, a namespaced custom meta key, an unknown "
        "frame key and an unknown event type: a consumer ignores them",
        _lines([_header(spec_version="1.3", **{"acme.session_tag": "k10"},
                        meta={**META, "acme.gain": 2.5}),
                {**_frames(rows)[0], "acme.debug": {"lag_ms": 3}}, *_frames(rows)[1:],
                {"type": "acme.marker", "t": 0.21, "note": "ignored"}, end]))
    add("K11", "v0.1", "k11-unknown-major.jsonl", "jsonl-stream", "reject", ["HDR-2", "VER-5"],
        'Header spec_version "2.0": an unknown major version', _lines([_header(spec_version="2.0"), *_frames(rows), end]),
        failing_checks=["NTS-VERSION"], schema_class="schema")
    add("K12", "v0.1", "k12-decision-pointer.jsonl", "jsonl-stream", "accept", ["DEC-2", "DEC-3", "DEC-4", "PTR-1"],
        "A command stream with decision events (calibrated_prob) and a pointer event (the v0.1 control forms)",
        _lines([_header(vocab=["rest", "select", "next"], vocab_type="command", blank_id=None),
                {"type": "frame", "t": 0.0, "log_probs": [round(math.log(p), 4) for p in (0.7, 0.2, 0.1)]},
                {"type": "decision", "t": 0.04, "label": "select", "score": 0.82, "score_semantics": "calibrated_prob"},
                {"type": "pointer", "t": 0.04, "dims": 2, "mode": "absolute", "values": [0.5, 0.25]}, end]))
    add("K13", "v0.1", "k13-modality-keys.jsonl", "jsonl-stream", "accept", ["MET-1", "MET-7"],
        "EMG modality keys from the semantic-convention registry (emg.placement, emg.derivation)",
        _lines([_header(meta={**META, "emg.placement": "wrist", "emg.derivation": "bipolar"}), *_frames(rows), end]))
    add("K14", "v0.1", "k14-bad-weights-hash.jsonl", "jsonl-stream", "reject", ["MET-1"],
        "decoder.weights_sha256 is not 64 lowercase hex digits",
        _lines([_header(meta={**META, "decoder.weights_sha256": "ABC123"}), *_frames(rows), end]),
        failing_checks=["NTS-META-TYPES"], schema_class="semconv")
    # K32 (P1-16, MET-11): an advisory finding. K33-K36 (P7-02): accepted streams that stop below provenance;
    # a Trust-ready consumer must report their stream level (spec 9.6).
    add("K32", "v0.1", "k32-modality-mismatch.jsonl", "jsonl-stream", "accept-with-warnings", ["MET-11"],
        "EMG keys (emg.placement, emg.derivation) on a stream whose device.modality is eeg: the modality match of MET-11 "
        "is a SHOULD NOT, so it is a warning only",
        _lines([_header(meta={**META, "device.modality": "eeg", "emg.placement": "wrist", "emg.derivation": "bipolar"}),
                *_frames(rows), end]), warning_checks=["NTS-MODALITY-MATCH"])
    add("K33", "v0.1", "k33-core-only.jsonl", "jsonl-stream", "accept", ["HDR-7", "CNF-3"],
        "A valid stream with no source and no meta: it reaches stream level core only (trust-ready needs source, "
        "device.modality, decoder.causal, data.derived and language)",
        _lines([{k: v for k, v in _header().items() if k not in ("source", "meta")}, *_frames(rows), end]),
        stream_level="core")
    no_pv = {k: v for k, v in META.items() if not k.startswith(("decoder.name", "decoder.version", "decoder.weights",
                                                                 "adapter.", "stream."))}
    add("K34", "v0.1", "k34-trust-ready-no-provenance.jsonl", "jsonl-stream", "accept", ["CNF-3", "CNF-4"],
        "A stream with the trust-ready keys but without stream.id, decoder name and version and weights hash: it "
        "reaches stream level trust-ready, not provenance",
        _lines([_header(meta=no_pv), *_frames(rows), end]), stream_level="trust-ready")
    add("K35", "v0.1", "k35-offline-with-latency.jsonl", "jsonl-stream", "accept", ["MET-5", "CNF-3"],
        "Timing: an offline decoder (decoder.causal false) that still writes latency 0.2: MET-5 says it SHOULD omit "
        "latency, so the stream stays at level core",
        _lines([_header(latency=0.2, meta={**META, "decoder.causal": False}), *_frames(rows), end]), stream_level="core")
    add("K36", "v0.1", "k36-calibration-without-method.jsonl", "jsonl-stream", "accept", ["MET-6", "DEC-5", "CNF-3"],
        "Score semantics: calibration.applied is true but decoder.calibration_method is absent, so a trust layer "
        "cannot tell how the probabilities were calibrated; the stream stays at level core",
        _lines([_header(meta={**META, "calibration.applied": True}), *_frames(rows), end]), stream_level="core")

    # --- fep-0001: text trust events --------------------------------------------------------------
    decl = {"decoder": "kit-beam", "decoder_version": "1.0", "frame_temperature": 1.0,
            "params": {"beam": 8}, "config_id": CFG_T}
    add("K15", "fep-0001", "k15-text-trust-input.jsonl", "jsonl-stream", "accept",
        ["SEG-4", "SEG-5", "EVD-1", "EVD-3", "EVD-4", "DCL-1", "HYP-1"],
        "Input of a text trust layer: decode_declaration, frames, a hypothesis with evidence fields, segment_end",
        _lines([_header(decode_declaration=decl), *_frames(rows),
                {"type": "hypothesis", "id": "h1", "is_final": True, "score_semantics": "none",
                 "nbest": [{"text": "ab ", "score": -1.1, "char_confidences": [0.91, 0.84, 0.77],
                            "logp_acoustic": -1.4, "logp_lm": -2.2}]},
                {"type": "segment_end", "t": 0.24, "unit": "utterance"}, end]))
    td = {"type": "trust_decision", "spec_version": SV, "session": "u1", "utterance": 0,
          "score_semantics": "calibrated_prob", "shown": ["ab "], "config_id": CFG_T}
    log = [{**td, "seq": 0, "is_final": False, "action": "OFFER", "p_top1": 0.71},
           {**td, "seq": 1, "is_final": True, "action": "COMMIT", "p_top1": 0.93}]
    add("K16", "fep-0001", "k16-text-decision-log.jsonl", "jsonl-decision-log", "accept",
        ["TD-F1", "TD-F2", "TD-5", "TD-6", "TD-8", "VER-1"],
        "Text decision log: a provisional OFFER, then one final COMMIT", _lines(log))
    add("K17", "fep-0001", "k17-commit-empty-shown.jsonl", "jsonl-decision-log", "reject", ["TD-8"],
        "A final COMMIT with an empty shown list", _lines([{**log[1], "seq": 0, "shown": []}]),
        failing_checks=["FEP1-TD-FORMAT"], schema_class="schema")
    add("K18", "fep-0001", "k18-two-finals.jsonl", "jsonl-decision-log", "reject", ["TD-6"],
        "Two final decisions for the same utterance", _lines([log[1], {**log[1], "seq": 2}]),
        failing_checks=["FEP1-TD-FINAL"], schema_class="cross-line")

    # --- fep-0003: intent profile -----------------------------------------------------------------
    ivocab = ["intent.rest", "intent.select", "intent.next", "intent.undo", "intent.confirm", "intent.call-caregiver"]
    idecl = {"vocab_id": "intent.kit-home", "vocab_version": "1", "intents": [
        {"id": "intent.rest", "risk": "safe", "role": "null"}, {"id": "intent.select", "risk": "undoable"},
        {"id": "intent.next", "risk": "safe"}, {"id": "intent.undo", "risk": "undoable", "role": "undo"},
        {"id": "intent.confirm", "risk": "irreversible", "role": "confirm"},
        {"id": "intent.call-caregiver", "risk": "irreversible", "label": "call the caregiver"}]}
    ihdr = _header(vocab=ivocab, vocab_type="command", blank_id=None, intent_declaration=idecl)
    intents = [{"type": "intent", "id": "u1", "t": 1.0, "is_final": True, "score_semantics": "calibrated_prob",
                "candidates": [{"intent": "intent.select", "score": 0.88}, {"intent": "intent.next", "score": 0.07}]},
               {"type": "intent", "id": "u2", "t": 2.0, "is_final": True, "score_semantics": "calibrated_prob",
                "candidates": [{"intent": "intent.rest", "score": 0.9}]}]
    add("K19", "fep-0003", "k19-intent-stream.jsonl", "jsonl-stream", "accept",
        ["INT-D1", "INT-D2", "INT-D3", "INT-D4", "INT-D5", "INT-E1", "INT-E2", "INT-E3", "INT-E4", "PRF-3"],
        "Intent stream: intent_declaration in the header, two final intent events", _lines([ihdr, *intents, end]))
    add("K20", "fep-0003", "k20-intent-undeclared.jsonl", "jsonl-stream", "reject", ["INT-E2"],
        "An intent event names an intent that the declaration does not list",
        _lines([ihdr, {**intents[0], "candidates": [{"intent": "intent.open-door", "score": 0.8}]}, end]),
        failing_checks=["FEP3-INTENT"], schema_class="cross-line")
    itd = {"type": "trust_decision", "spec_version": SV, "profile": "intent", "session": "u1",
           "score_semantics": "calibrated_prob", "config_id": CFG_I, "vocab_id": "intent.kit-home"}
    ilog = [{**itd, "seq": 0, "unit": 0, "is_final": True, "action": "COMMIT", "reason": "p 0.97 >= 0.90",
             "p_top1": 0.97, "risk_class": "undoable", "threshold": 0.9, "intent": "intent.select", "role": "action"},
            {**itd, "seq": 1, "unit": 1, "is_final": True, "action": "ABSTAIN", "reason": "top intent is null",
             "p_top1": 0.9, "risk_class": "safe", "threshold": 0.9, "role": "null"}]
    add("K21", "fep-0003", "k21-intent-decision-log.jsonl", "jsonl-decision-log", "accept",
        ["INT-T1", "INT-T2", "INT-T3", "INT-S1", "PRF-4"],
        "Intent decision log: COMMIT of an undoable intent, ABSTAIN on the null intent", _lines(ilog))
    add("K22", "fep-0003", "k22-intent-irreversible-direct.jsonl", "jsonl-decision-log", "reject", ["INT-S4"],
        "A direct COMMIT of an irreversible intent without the confirm step (safety rule)",
        _lines([{**itd, "seq": 0, "unit": 0, "is_final": True, "action": "COMMIT", "reason": "confirmed",
                 "p_top1": 0.996, "risk_class": "irreversible", "threshold": 0.99, "intent": "intent.call-caregiver",
                 "role": "action", "confirmed_via": "intent"}]),
        failing_checks=["FEP3-SAFETY"], schema_class="trust")

    # --- fep-0005: control profile ----------------------------------------------------------------
    cdecl = {"dims": 2, "quantity": "velocity", "units": "mm/s", "frame": "workspace", "rate_hz": 50.0,
             "uncertainty": "std", "axes": ["x", "y"], "max_speed": 400.0, "latency_s": 0.1, "window_s": 0.2}
    chdr = _header(vocab=["control"], vocab_type="command", blank_id=None, control_declaration=cdecl)
    ctl = [{"type": "control_enable", "t": 0.0, "enabled": True, "source": "switch"},
           {"type": "control", "t": 0.02, "tick": 0, "values": [40.0, -12.5], "std": [15.0, 15.0]},
           {"type": "control", "t": 0.04, "tick": 1, "values": [55.0, -20.0], "std": [15.0, 15.0]},
           {"type": "control_enable", "t": 0.05, "enabled": False, "source": "switch", "reason": "user switch"}]
    add("K23", "fep-0005", "k23-control-stream.jsonl", "jsonl-stream", "accept",
        ["CTL-D1", "CTL-D2", "CTL-1", "CTL-2", "CTL-3", "CTL-4", "CTL-E1"],
        "Control stream: control_declaration, engage, two velocity ticks with std, disengage", _lines([chdr, *ctl, end]))
    add("K24", "fep-0005", "k24-control-dims.jsonl", "jsonl-stream", "reject", ["CTL-4"],
        "A control tick has three values for a 2-D declaration",
        _lines([chdr, ctl[0], {**ctl[1], "values": [1.0, 2.0, 3.0]}, end]),
        failing_checks=["FEP5-CONTROL"], schema_class="cross-line")
    ctd = {"type": "trust_decision", "spec_version": SV, "profile": "control", "session": "c1", "t": 0.02,
           "is_final": True, "units": "mm/s", "p_top1": None, "score_semantics": "calibrated_prob", "authority": 1.0,
           "engagement": 1, "v_max": 400.0, "ttl_s": 0.06, "config_id": CFG_C}
    clog = [{**ctd, "seq": 0, "tick": 0, "action": "ABSTAIN", "state": "hold", "velocity": [0.0, 0.0],
             "raw": [40.0, -12.0], "gain": 0.0, "reasons": ["not_engaged"], "reason": "not_engaged",
             "score_semantics": "none", "engagement": 0},
            {**ctd, "seq": 1, "tick": 1, "action": "COMMIT", "state": "act", "velocity": [40.0, -12.0],
             "raw": [40.0, -12.0], "gain": 1.0, "reasons": ["ok"], "reason": "ok", "radius": 10.0, "level": 0.9}]
    add("K25", "fep-0005", "k25-control-decision-log.jsonl", "jsonl-decision-log", "accept",
        ["CTL-T1", "CTL-T2", "CTL-T3", "CTL-T4", "CTL-T5", "CTL-S1"],
        "Control decision log: hold before engage, then one acting tick", _lines(clog))

    # --- fep-0002: LSL binding ------------------------------------------------------------------
    lh = {k: v for k, v in _header().items() if k != "type"}
    lrows = [[float(np.float32(x)) for x in r] for r in rows]
    stamps = [500.0 + i * FP for i in range(len(lrows))]
    last = stamps[-1]
    lev = [{"type": "segment_end", "t": last + 0.01}, {"type": "end"}]

    def lsl_capture(desc: str, frames_xml: str) -> dict[str, Any]:
        return L._scenario("inlet", desc, route="frames", inlets={
            "primary": L._inlet_spec(frames_xml, L._chunks(lrows, stamps), 0.1),
            "events": L._inlet_spec(L._events_xml(header=lh), L._markers(lev, [last + 0.01, last + 0.02]), 0.1)})

    add("K26", "fep-0002", "k26-lsl-capture.json", "lsl-capture", "accept",
        ["LSL-F1", "LSL-F2", "LSL-F3", "LSL-D1", "LSL-D2", "LSL-E1", "LSL-C2", "LSL-V1"],
        "LSL capture: a float32 NTS frames stream (5 channels) and its Markers events stream, receiver clock",
        _json(lsl_capture("kit LSL capture", L._frames_xml(header=lh, srate=1 / FP))))
    add("K27", "fep-0002", "k27-lsl-channel-count.json", "lsl-capture", "reject", ["LSL-F2"],
        "LSL frames stream with 4 channels for a 5-token vocab",
        _json(lsl_capture("kit channel count", L._frames_xml(header=lh, srate=1 / FP, n=4, labels=VOCAB5[:4]))),
        failing_checks=["FEP2-CONSUME", "FEP2-FRAMES"], schema_class="binding")
    add("K28", "fep-0002", "k28-lsl-decisions.json", "lsl-decisions-capture", "accept", ["LSL-X1", "LSL-X2", "TD-6"],
        "LSL fidetype.decisions stream: a provisional OFFER, then a final COMMIT",
        _json(L._decisions("kit LSL decisions", [L._td(seq=0, is_final=False, action="OFFER", p_top1=0.71),
                                                 L._td(seq=1)])))

    # --- fep-0004: WebSocket binding ------------------------------------------------------------
    wev = W._numbered(_frames(rows) + [{"type": "segment_end"}, end])
    whdr = {**_header(), "ws": {"binding": "nts-ws/0.1", "stream_id": "kit-1"}}
    add("K29", "fep-0004", "k29-ws-session.json", "ws-capture", "accept",
        ["WS-H2", "WS-S1", "WS-Q1", "WS-Q2", "WS-F1", "WS-V1"],
        "WebSocket /nts session: subprotocol nts-ws.0.1, header, six frames and segment_end with ws_seq 1-8, clean close",
        _json(W._ingest("kit WebSocket session", [W._open(), {"at": 0.0, "conn": 1, "msg": whdr}] + W._msgs(wev)
                        + [{"at": 0.5, "conn": 1, "close": True}])))
    add("K30", "fep-0004", "k30-ws-first-not-header.json", "ws-capture", "reject", ["WS-S1"],
        "The first WebSocket message is a frame, not the header",
        _json(W._ingest("kit first not header", [W._open()] + W._msgs(wev))),
        failing_checks=["FEP4-HANDSHAKE"], schema_class="cross-line")
    wdec = [W._td(1, 0, 0, final=False, action="OFFER", text="ab "), W._td(2, 1, 0, text="ab ")]
    add("K31", "fep-0004", "k31-ws-decisions.json", "ws-decisions-capture", "accept", ["WS-D1", "WS-D2", "TD-6"],
        "WebSocket /decisions channel: welcome, a provisional OFFER, a final COMMIT",
        _json(W._scenario("subscribe", "kit decisions", messages=[W.WELCOME] + wdec)))
    return ks


# --- writing and reading ----------------------------------------------------------------------


def kit_dir() -> Path:
    """``spec/conformance/kit`` of the repository, else the copy in the installed wheel."""
    repo = Path(__file__).resolve().parents[3] / "spec" / "conformance" / "kit"
    if repo.is_dir():
        return repo
    return Path(__file__).resolve().parents[1] / "_spec" / "conformance" / "kit"


def write_kit(out_dir: str | PathLike[str]) -> dict[str, Any]:
    """Write every kit file, one manifest per profile, ``kit.json`` and ``rule-map.json``. Returns the index."""
    from fidetype.conformance.profiles import get_profile
    from fidetype.conformance.rules import SPEC_LABEL, render_rule_map

    out = Path(out_dir)
    entries = build_kit()
    by_prof: dict[str, list[KitEntry]] = {}
    for e in entries:
        by_prof.setdefault(e.profile, []).append(e)
    for prof, es in by_prof.items():
        d = out / prof
        d.mkdir(parents=True, exist_ok=True)
        for e in es:
            e.writer(d / e.file)
        man = {"schema": MANIFEST_SCHEMA, "spec_version": SV, "profile": prof,
               "fep": None if prof == "v0.1" else get_profile(prof).fep, "kit": KIT_SCHEMA,
               "generator": "nts-conform build --out spec/conformance/kit", "how_to_use": HOW_TO_USE,
               "vectors": [e.to_manifest() for e in es]}
        (d / "manifest.json").write_text(json.dumps(man, indent=1, ensure_ascii=False) + "\n", encoding="utf-8",
                                         newline="\n")
    index = {"schema": KIT_SCHEMA, "kit_version": KIT_VERSION, "spec": SPEC_LABEL,
             "generator": "nts-conform build --out spec/conformance/kit", "licence": "Apache-2.0",
             "how_to_use": HOW_TO_USE, "verdicts": list(VERDICTS), "wire_forms": WIRE_FORMS,
             "not_in_kit": {"binary protobuf": "not a wire form in RC4 (framing is roadmap P1-05); the JSON Lines "
                                               "files are the proto JSON mapping",
                            "HID bridge, gRPC, Arrow, BLE": "not defined in RC4 (8.4)"},
             "entries": [e.to_index() for e in entries]}
    (out / "kit.json").write_text(json.dumps(index, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    (out / "rule-map.json").write_text(render_rule_map(), encoding="utf-8", newline="\n")
    return index


def load_index(kit: str | PathLike[str] | None = None) -> dict[str, Any]:
    root = Path(kit) if kit is not None else kit_dir()
    return json.loads((root / "kit.json").read_text(encoding="utf-8"))


__all__ = ["KIT_SCHEMA", "LEVELLED_FORMS", "STREAM_LEVELS", "VERDICTS", "WIRE_FORMS", "KitEntry", "build_kit", "kit_dir", "load_index", "write_kit"]
