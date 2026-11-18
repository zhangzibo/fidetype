"""Golden test vectors for NeuralTextStream v0.1 consumers.

Each vector is a small stream file (NPZ or JSON Lines) and an expected
outcome: ``accept`` or ``reject``. For an accepted file the manifest also
gives values that a correct consumer reads (number of frames, the
``vocab_type`` after defaults, the number of ``-inf`` cells, the number
of ignored events). The vectors cover the 20 cases of spec 7.1 (C1-C20)
and more edge cases.

The committed copy lives in ``spec/conformance/v0.1/`` (``manifest.json``
plus the files). Regenerate it with::

    python -m fidetype.conformance vectors --out spec/conformance/v0.1

All content is synthetic (fixed random seed). No data from people.
"""

from __future__ import annotations

import json
import math
import shlex
import subprocess
from dataclasses import dataclass, field
from os import PathLike
from pathlib import Path
from typing import Any, Callable

import numpy as np

from fidetype.streams.spec import NeuralTextStream
from fidetype.streams.vocab import VOCAB

MANIFEST_SCHEMA = "fidetype.conformance.vectors/1"

KEY_VOCAB = [*(f"Key{c}" for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"), "Space", "Backspace"]
PHONEME_VOCAB = ["<blank>", "SIL", "AA", "AE", "AH", "B", "D", "K", "S", "T"]
COMMAND_VOCAB = ["rest", "select", "next", "back"]
SHA = "3f1c0d4e5b6a79881726354433221100ffeeddccbbaa99887766554433221100"


@dataclass
class Vector:
    vid: str
    file: str
    expect: str  # accept | reject
    clause: str
    description: str
    case: str | None = None
    expected: dict[str, Any] = field(default_factory=dict)
    failing_check: str | None = None
    writer: Callable[[Path], None] | None = None

    def to_manifest(self) -> dict[str, Any]:
        d = {"id": self.vid, "file": self.file, "format": Path(self.file).suffix.lstrip("."), "expect": self.expect,
             "spec_case": self.case, "clause": self.clause, "description": self.description}
        if self.expected:
            d["expected"] = self.expected
        if self.failing_check:
            d["failing_check"] = self.failing_check
        return d


# --- builders -----------------------------------------------------------------------


def _lsm(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)
    m = x.max(axis=1, keepdims=True)
    return x - m - np.log(np.exp(x - m).sum(axis=1, keepdims=True))


def _rng() -> np.random.Generator:
    return np.random.default_rng(20261111)


def _lp(T: int, V: int, seed: int = 0) -> np.ndarray:
    return _lsm(np.random.default_rng(seed).standard_normal((T, V)) * 2.0)


BASE_META = {"device.modality": "other", "decoder.name": "conformance-vector", "decoder.version": "1",
             "decoder.causal": True, "data.derived": True, "language": "en"}


def _npz_arrays(T: int = 6, V: int | None = None, vocab: list[str] | None = None, seed: int = 0,
                **over: Any) -> dict[str, np.ndarray]:
    vocab = list(VOCAB) if vocab is None else vocab
    V = len(vocab) if V is None else V
    a: dict[str, Any] = dict(
        version=np.array("0.1"),
        log_probs=_lp(T, V, seed).astype(np.float32),
        frame_times=(np.arange(T) * 0.04).astype(np.float64),
        vocab=np.array(vocab, dtype=np.str_),
        vocab_type=np.array("char"),
        blank_id=np.array(0, dtype=np.int64),
        source=np.array("conformance-vector"),
        meta_json=np.array(json.dumps(BASE_META)),
        frame_period=np.array(0.04, dtype=np.float64),
        latency=np.array(0.0, dtype=np.float64),
    )
    for k, v in over.items():
        if v is None:
            a.pop(k, None)
        else:
            a[k] = v
    return a


def _w_npz(**kw: Any) -> Callable[[Path], None]:
    def w(path: Path) -> None:
        np.savez_compressed(path, **_npz_arrays(**kw))

    return w


def _w_npz_raw(arrays: dict[str, Any], allow_pickle_objects: bool = False) -> Callable[[Path], None]:
    def w(path: Path) -> None:
        if allow_pickle_objects:
            np.savez(path, **arrays)  # object arrays are pickled
        else:
            np.savez_compressed(path, **arrays)

    return w


def _row(v: np.ndarray) -> list[float | None]:
    return [None if x == -math.inf else round(float(x), 6) for x in v]


def _header(vocab: list[str] | None = None, **over: Any) -> dict[str, Any]:
    h = {"type": "header", "spec_version": "0.1", "vocab": list(VOCAB) if vocab is None else vocab,
         "vocab_type": "char", "blank_id": 0, "source": "conformance-vector", "frame_period": 0.04,
         "latency": 0.0, "clock_domain": "trial", "meta": dict(BASE_META)}
    for k, v in over.items():
        if v is _DROP:
            h.pop(k, None)
        else:
            h[k] = v
    return h


_DROP = object()


def _frames(T: int, V: int, seed: int = 0, dt: float = 0.04) -> list[dict[str, Any]]:
    lp = _lp(T, V, seed)
    return [{"type": "frame", "t": round(i * dt, 6), "log_probs": _row(lp[i])} for i in range(T)]


def _w_lines(objs: list[Any], raw_lines: list[str] | None = None) -> Callable[[Path], None]:
    def w(path: Path) -> None:
        lines = [json.dumps(o, ensure_ascii=False) for o in objs]
        if raw_lines:
            lines += raw_lines
        path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    return w


# --- the vector set -----------------------------------------------------------------------


def build_vectors() -> list[Vector]:
    V = len(VOCAB)
    vs: list[Vector] = []

    def add(*a: Any, **k: Any) -> None:
        vs.append(Vector(*a, **k))

    # Frame core, NPZ (spec 7.1 C1-C15)
    add("V01", "v01-char-valid.npz", "accept", "3.1 / 6.1", "Valid char stream, 28 tokens, CTC blank at 0", "C1",
        {"n_frames": 6, "vocab_size": 28, "vocab_type": "char", "blank_id": 0}, writer=_w_npz())
    add("V03", "v03-command-no-blank.npz", "accept", "3.1", "Valid command stream, blank_id null (-1 in NPZ)", "C2",
        {"n_frames": 6, "vocab_type": "command", "blank_id": None},
        writer=_w_npz(vocab=COMMAND_VOCAB, vocab_type=np.array("command"), blank_id=np.array(-1, dtype=np.int64)))
    add("V04", "v04-empty.npz", "accept", "3.0", "Empty stream (T = 0)", "C3", {"n_frames": 0},
        writer=_w_npz(T=0))
    add("V06", "v06-single-frame.npz", "accept", "3.1", "Single frame", None, {"n_frames": 1}, writer=_w_npz(T=1))
    one_hot = np.full((3, V), -np.inf, dtype=np.float32)
    one_hot[:, 0] = 0.0
    add("V07", "v07-minus-inf-row.npz", "accept", "5.2.2", "Rows of -inf except one 0", "C4",
        {"n_frames": 3, "neg_inf_cells": 3 * (V - 1)}, writer=_w_npz(T=3, log_probs=one_hot))
    two = _lp(4, V, 1).astype(np.float32)
    two[2] += np.float32(math.log(2.0))
    add("V08", "v08-row-sums-to-2.npz", "reject", "5.2.1", "A row sums to 2 in probability space", "C5",
        failing_check="NTS-NORM", writer=_w_npz(T=4, log_probs=two))
    nan = _lp(4, V, 2).astype(np.float32)
    nan[1, 3] = np.nan
    add("V09", "v09-nan.npz", "reject", "5.2.2", "NaN in log_probs", "C6", failing_check="NTS-LP-FINITE",
        writer=_w_npz(T=4, log_probs=nan))
    pinf = _lp(4, V, 3).astype(np.float32)
    pinf[0, 0] = np.inf
    add("V10", "v10-plus-inf.npz", "reject", "5.2.2", "+inf in log_probs", "C6", failing_check="NTS-LP-FINITE",
        writer=_w_npz(T=4, log_probs=pinf))
    add("V11", "v11-equal-times.npz", "reject", "5.2.3", "Two equal frame_times", "C7", failing_check="NTS-FT-MONO",
        writer=_w_npz(T=4, frame_times=np.array([0.0, 0.04, 0.04, 0.12])))
    dup = list(VOCAB)
    dup[5] = "a"
    add("V12", "v12-duplicate-token.npz", "reject", "5.2.4", "Duplicate token in vocab", "C8",
        failing_check="NTS-VOCAB-UNIQUE", writer=_w_npz(vocab=dup))
    add("V13", "v13-v-mismatch.npz", "reject", "5.1.2", "V differs from the length of vocab", "C9",
        failing_check="NTS-V-MATCH", writer=_w_npz(V=27))
    add("V14", "v14-blank-out-of-range.npz", "reject", "5.1.6", "blank_id = V", "C10", failing_check="NTS-BLANK",
        writer=_w_npz(blank_id=np.array(V, dtype=np.int64)))
    add("V15", "v15-unknown-vocab-type.npz", "reject", "5.1.5", "Unknown vocab_type", "C11",
        failing_check="NTS-VOCAB-TYPE", writer=_w_npz(vocab_type=np.array("glyph")))
    add("V16", "v16-unknown-version.npz", "reject", "5.1.4", 'Unknown spec_version "9.9"', "C12",
        failing_check="NTS-VERSION", writer=_w_npz(version=np.array("9.9")))
    add("V17", "v17-future-minor-version.npz", "reject", "5.1.4 / 6.1", 'Future minor version "0.2" (see ambiguity A6)',
        None, failing_check="NTS-VERSION", writer=_w_npz(version=np.array("0.2")))
    add("V18", "v18-negative-latency.npz", "reject", "5.2.5", "Negative latency", "C13", failing_check="NTS-LATENCY",
        writer=_w_npz(latency=np.array(-0.01)))
    add("V19", "v19-zero-frame-period.npz", "reject", "5.2.5", "frame_period = 0", "C13",
        failing_check="NTS-FRAME-PERIOD", writer=_w_npz(frame_period=np.array(0.0)))
    add("V20", "v20-no-vocab-type.npz", "accept", "6.1", "NPZ without vocab_type: read as char", "C14",
        {"vocab_type": "char", "vocab_type_defaulted": True}, writer=_w_npz(vocab_type=None))
    add("V21", "v21-unknown-npz-key.npz", "accept", "6.1", "NPZ with an unknown extra key: ignore it", "C15",
        {"n_frames": 6, "unknown_keys": ["acme_extra"]}, writer=_w_npz(acme_extra=np.arange(3)))
    add("V22", "v22-key-vocab.npz", "accept", "3.1 / 8.2", "Key stream (W3C codes), no blank", None,
        {"vocab_type": "key", "blank_id": None, "vocab_size": len(KEY_VOCAB)},
        writer=_w_npz(vocab=KEY_VOCAB, vocab_type=np.array("key"), blank_id=np.array(-1, dtype=np.int64)))
    add("V23", "v23-unnormalised-logits.npz", "reject", "5.2.1", "Raw logits instead of log_softmax output", None,
        failing_check="NTS-NORM",
        writer=_w_npz(log_probs=(np.random.default_rng(4).standard_normal((6, V)) * 3).astype(np.float32)))
    allneg = _lp(3, V, 5).astype(np.float32)
    allneg[1] = -np.inf
    add("V24", "v24-all-minus-inf-row.npz", "reject", "5.2.1", "A row of only -inf (total probability 0)", None,
        failing_check="NTS-NORM", writer=_w_npz(T=3, log_probs=allneg))
    add("V25", "v25-meta-nan.npz", "reject", "4.1", "meta_json holds NaN (not a JSON value)", None,
        failing_check="NTS-META-JSON", writer=_w_npz(meta_json=np.array('{"acme.gain": NaN}')))
    add("V26", "v26-pickled-object.npz", "reject", "6.1", "vocab stored as a pickled object array", None,
        failing_check="NTS-PARSE",
        writer=_w_npz_raw(_npz_arrays(vocab=list(VOCAB)) | {"vocab": np.array(list(VOCAB), dtype=object)},
                          allow_pickle_objects=True))
    add("V27", "v27-float64-log-probs.npz", "accept", "6.1", "log_probs stored as float64 (table says float32; see A7)",
        None, {"n_frames": 6}, writer=_w_npz(log_probs=_lp(6, V, 0)))
    add("V28", "v28-missing-meta-json.npz", "reject", "6.1", "Required NPZ key meta_json missing", None,
        failing_check="NTS-NPZ-KEYS", writer=_w_npz(meta_json=None))
    add("V29", "v29-provenance-valid.npz", "accept", "4.2 / 4.3", "All four provenance keys, valid", None,
        {"n_frames": 6},
        writer=_w_npz(meta_json=np.array(json.dumps(BASE_META | {
            "stream.id": "6f1d2c0e9b8a4f3e", "decoder.weights_sha256": SHA,
            "adapter.name": "acme-adapter", "adapter.version": "1.2.0"}))))
    add("V30", "v30-bad-weights-sha.npz", "reject", "4.1 / 4.2", "decoder.weights_sha256 is not 64 lowercase hex", None,
        failing_check="NTS-META-TYPES",
        writer=_w_npz(meta_json=np.array(json.dumps(BASE_META | {"decoder.weights_sha256": SHA.upper()[:40]}))))
    add("V31", "v31-lookahead-mismatch.npz", "reject", "4.2", "decoder.lookahead_s differs from latency", None,
        failing_check="NTS-META-LOOKAHEAD",
        writer=_w_npz(latency=np.array(0.2), meta_json=np.array(json.dumps(BASE_META | {"decoder.lookahead_s": 0.1}))))
    add("V32", "v32-bad-modality.npz", "reject", "4.1 / 4.2", 'device.modality "ultrasound" is not in the enum', None,
        failing_check="NTS-META-TYPES",
        writer=_w_npz(meta_json=np.array(json.dumps(BASE_META | {"device.modality": "ultrasound"}))))
    add("V33", "v33-leak-target-text.npz", "reject", "5.3.1", "meta carries the target text (heuristic check)", None,
        failing_check="NTS-LEAK-KEYS",
        writer=_w_npz(meta_json=np.array(json.dumps(BASE_META | {"acme.target_text": "hola mundo"}))))
    add("V34", "v34-unknown-meta-keys.npz", "accept", "4.1", "Custom namespaced meta keys: allowed", None,
        {"n_frames": 6}, writer=_w_npz(meta_json=np.array(json.dumps(BASE_META | {"acme.gain": 3, "acme.mode": "x"}))))

    # JSON Lines (6.2) and Development events (3.3-3.9)
    add("V02", "v02-char-valid.jsonl", "accept", "6.2", "Valid char stream in JSON Lines with an end line", "C1",
        {"n_frames": 5, "vocab_type": "char", "blank_id": 0},
        writer=_w_lines([_header(), *_frames(5, V), {"type": "end"}]))
    add("V05", "v05-empty.jsonl", "accept", "6.2.6", "Header only, no frames, no end line", "C3", {"n_frames": 0},
        writer=_w_lines([_header()]))
    f = _frames(3, V, 6)
    f[1]["log_probs"][4] = None
    f[1]["log_probs"] = _row(_lsm(np.array([[(-math.inf if x is None else x) for x in f[1]["log_probs"]]]))[0])
    add("V35", "v35-null-is-minus-inf.jsonl", "accept", "6.2.3", "null in log_probs reads as -inf", "C16",
        {"n_frames": 3, "neg_inf_cells": 1}, writer=_w_lines([_header(), *f, {"type": "end"}]))
    add("V36", "v36-decision-prob-out-of-range.jsonl", "reject", "3.5", "decision, uncalibrated_prob, score 1.5", "C17",
        failing_check="NTS-EVT-DECISION",
        writer=_w_lines([_header(), *_frames(2, V), {"type": "decision", "t": 0.1, "label": "a", "score": 1.5,
                                                     "score_semantics": "uncalibrated_prob"}]))
    add("V37", "v37-strength-no-range.jsonl", "reject", "3.5", "decision, strength, no score_range", "C18",
        failing_check="NTS-EVT-DECISION",
        writer=_w_lines([_header(), *_frames(2, V), {"type": "decision", "t": 0.1, "label": "a", "score": 200,
                                                     "score_semantics": "strength"}]))
    add("V38", "v38-unknown-event-type.jsonl", "accept", "6.2.5", "Unknown event type: ignore the event", "C19",
        {"n_frames": 2, "ignored_events": 1},
        writer=_w_lines([_header(), *_frames(2, V), {"type": "acme.heartbeat", "t": 0.05, "x": 1}, {"type": "end"}]))
    add("V39", "v39-timing-order.jsonl", "reject", "3.8", "t_decoded earlier than t_signal_end", "C20",
        failing_check="NTS-EVT-TIMING",
        writer=_w_lines([_header(), *_frames(2, V), {"type": "decision", "t": 0.1, "label": "a", "score": None,
                                                     "score_semantics": "none", "t_signal_start": 0.0,
                                                     "t_signal_end": 0.5, "t_decoded": 0.4, "t_emitted": 0.6}]))
    add("V40", "v40-unknown-keys.jsonl", "accept", "6.2.5", "Unknown header keys, frame keys and meta keys: ignore", None,
        {"n_frames": 2, "unknown_keys": ["acme_header_extra"]},
        writer=_w_lines([_header(acme_header_extra={"a": 1}, meta=BASE_META | {"acme.x": 1}),
                         *[fr | {"acme_frame_extra": True} for fr in _frames(2, V)]]))
    add("V41", "v41-nan-token.jsonl", "reject", "6.2 / 5.2.2", "JSON NaN token in log_probs (not valid JSON)", "C6",
        failing_check="NTS-PARSE",
        writer=_w_lines([_header()], [json.dumps({"type": "frame", "t": 0.0, "log_probs": [float("nan")] + [0.0] * (V - 1)})]))
    sp_ok = {"type": "frame", "t": 0.0, "top_ids": [0, 1], "top_log_probs": [round(math.log(0.6), 6), round(math.log(0.3), 6)],
             "rest_log_prob": round(math.log(0.1), 6)}
    add("V42", "v42-sparse-valid.jsonl", "accept", "3.3", "Sparse top-k frame plus rest mass", None,
        {"n_frames": 1}, writer=_w_lines([_header(), sp_ok]))
    sp_bad = dict(sp_ok, rest_log_prob=round(math.log(0.5), 6))
    add("V43", "v43-sparse-unnormalised.jsonl", "reject", "3.3", "Sparse frame: top-k plus rest sums to 1.4", None,
        failing_check="NTS-SPARSE", writer=_w_lines([_header(), sp_bad]))
    fr = _frames(3, V)
    fr[2]["t"] = 0.01
    add("V44", "v44-time-goes-back.jsonl", "reject", "6.2.4", "Frame t decreases", None, failing_check="NTS-FT-MONO",
        writer=_w_lines([_header(), *fr]))
    add("V45", "v45-header-not-first.jsonl", "reject", "6.2.1", "A frame comes before the header", None,
        failing_check="NTS-JSONL-HEADER", writer=_w_lines([*_frames(1, V), _header()]))
    fr = _frames(2, V)
    fr[1]["log_probs"] = fr[1]["log_probs"][:-1]
    add("V46", "v46-short-frame.jsonl", "reject", "5.1.2 / 6.2.2", "A frame with V-1 values", None,
        failing_check="NTS-V-MATCH", writer=_w_lines([_header(), *fr]))
    add("V47", "v47-blank-bool.jsonl", "reject", "3.1", "blank_id is a boolean", None, failing_check="NTS-BLANK",
        writer=_w_lines([_header(blank_id=True), *_frames(1, V)]))
    add("V48", "v48-lines-after-end.jsonl", "accept", "6.2", "Lines after the end marker: ignored (see A5)", None,
        {"n_frames": 1}, writer=_w_lines([_header(), *_frames(1, V), {"type": "end"}, *_frames(1, V)]))
    add("V49", "v49-phoneme-ctc.jsonl", "accept", "3.1 / 8.2", "Phoneme CTC stream (ARPAbet + SIL)", None,
        {"n_frames": 4, "vocab_type": "phoneme", "blank_id": 0},
        writer=_w_lines([_header(vocab=PHONEME_VOCAB, vocab_type="phoneme"), *_frames(4, len(PHONEME_VOCAB))]))
    add("V50", "v50-missing-header-field.jsonl", "reject", "6.2.1", "Header without vocab_type", None,
        failing_check="NTS-JSONL-HEADER", writer=_w_lines([_header(vocab_type=_DROP), *_frames(1, V)]))
    add("V51", "v51-events-valid.jsonl", "accept", "3.5-3.9", "Valid decision, hypothesis, pointer and signal_quality events",
        None, {"n_frames": 2, "events": 4},
        writer=_w_lines([_header(), *_frames(2, V),
                         {"type": "signal_quality", "t": 0.04, "value": 0.92, "unit": "index"},
                         {"type": "decision", "t": 0.08, "label": "a", "score": 0.71, "score_semantics": "uncalibrated_prob"},
                         {"type": "hypothesis", "id": "h1", "is_final": False, "score_semantics": "none",
                          "nbest": [{"text": "ab", "score": -1.2}, {"text": "a", "score": -1.9}]},
                         {"type": "pointer", "t": 0.08, "dims": 2, "mode": "absolute", "values": [0.5, 0.25]},
                         {"type": "end"}]))
    add("V52", "v52-bad-clock-domain.jsonl", "reject", "3.8", 'clock_domain "gps" is not in the enum', None,
        failing_check="NTS-CLOCK", writer=_w_lines([_header(clock_domain="gps"), *_frames(1, V)]))
    # --- NTS 1.0 RC2 (gap G-2): header spec_version "0.1" or "1.<minor>" (rules HDR-2, VER-3, VER-5)
    add("V53", "v53-version-1-0.jsonl", "accept", "1.0 RC2 11.2 (VER-3)", 'Header spec_version "1.0"', None,
        {"n_frames": 2}, writer=_w_lines([_header(spec_version="1.0"), *_frames(2, V), {"type": "end"}]))
    add("V54", "v54-version-1-3.jsonl", "accept", "1.0 RC2 11.2 (VER-3)",
        'Header spec_version "1.3" (a future minor version of major 1: read with the 1.0 rules)', None,
        {"n_frames": 2}, writer=_w_lines([_header(spec_version="1.3"), *_frames(2, V), {"type": "end"}]))
    add("V55", "v55-version-2-0.jsonl", "reject", "1.0 RC2 11.2 (VER-5)", 'Header spec_version "2.0" (unknown major version)',
        None, failing_check="NTS-VERSION", writer=_w_lines([_header(spec_version="2.0"), *_frames(1, V)]))
    add("V56", "v56-version-1-0-0.jsonl", "reject", "1.0 RC2 11.2 (VER-5)",
        'Header spec_version "1.0.0" (a patch level never appears in streams)', None,
        failing_check="NTS-VERSION", writer=_w_lines([_header(spec_version="1.0.0"), *_frames(1, V)]))
    add("V57", "v57-version-1-01.jsonl", "reject", "1.0 RC2 11.2 (VER-3, VER-5)",
        'Header spec_version "1.01" (a minor version with a leading zero)', None,
        failing_check="NTS-VERSION", writer=_w_lines([_header(spec_version="1.01"), *_frames(1, V)]))
    add("V58", "v58-version-01-0.jsonl", "reject", "1.0 RC2 11.2 (VER-5)",
        'Header spec_version "01.0" (a major version with a leading zero)', None,
        failing_check="NTS-VERSION", writer=_w_lines([_header(spec_version="01.0"), *_frames(1, V)]))
    add("V59", "v59-version-number.jsonl", "reject", "1.0 RC2 11.2 (VER-5)",
        "Header spec_version is the number 1.0, not a string", None,
        failing_check="NTS-VERSION", writer=_w_lines([_header(spec_version=1.0), *_frames(1, V)]))
    add("V60", "v60-version-1-0.npz", "accept", "1.0 RC2 11.2 (VER-3) / 8.1.2", 'NPZ with version "1.0"', None,
        {"n_frames": 6}, writer=_w_npz(version=np.array("1.0")))
    # --- NTS 1.0 RC2 (gap G-3): an integer field written with a fraction part (rule GEN-5)
    add("V61", "v61-blank-id-float.jsonl", "reject", "1.0 RC2 4.1 (GEN-5)", "Header blank_id is 0.0 (an integer written as 0.0)",
        None, failing_check="NTS-BLANK", writer=_w_lines([_header(blank_id=0.0), *_frames(1, V)]))
    # --- NTS 1.0 RC2 (HDR-12): V = 0 only if the stream has no frames (hypothesis-only producer)
    h0 = _header(vocab=[], blank_id=None, spec_version="1.0", frame_period=_DROP, latency=_DROP)
    hyp0 = [{"type": "hypothesis", "id": "u1", "is_final": True, "score_semantics": "none",
             "nbest": [{"text": "hello world", "score": 0.0}, {"text": "hello word", "score": 0.0}]},
            {"type": "segment_end", "unit": "utterance"},
            {"type": "hypothesis", "id": "u2", "is_final": True, "score_semantics": "none",
             "nbest": [{"text": "yes", "score": 0.0}]},
            {"type": "segment_end", "unit": "utterance"}]
    add("V62", "v62-empty-vocab-hypotheses.jsonl", "accept", "1.0 RC2 3.1 (HDR-12) / 4.7",
        "Hypothesis-only stream: vocab = [], blank_id null, hypotheses and segment ends, no frames", None,
        {"n_frames": 0, "vocab_size": 0, "blank_id": None, "events": 2},
        writer=_w_lines([h0, *hyp0, {"type": "end"}]))
    add("V63", "v63-empty-vocab-dense-frame.jsonl", "reject", "1.0 RC2 3.1 (HDR-12) / 4.2 (FRM-3)",
        "vocab = [] with a dense frame (log_probs = []): V = 0 needs a stream without frames", None,
        failing_check="NTS-NORM",
        writer=_w_lines([h0, hyp0[0], {"type": "frame", "t": 0.0, "log_probs": []}, {"type": "end"}]))
    add("V64", "v64-empty-vocab-sparse-frame.jsonl", "reject", "1.0 RC2 3.1 (HDR-12) / 4.2 (FRM-5)",
        "vocab = [] with a sparse frame (k = 0, rest_log_prob 0): V = 0 needs a stream without frames", None,
        failing_check="NTS-NORM",
        writer=_w_lines([h0, hyp0[0], {"type": "frame", "t": 0.0, "top_ids": [], "top_log_probs": [],
                                       "rest_log_prob": 0.0}, {"type": "end"}]))
    add("V65", "v65-empty-vocab-blank-0.jsonl", "reject", "1.0 RC2 3.1 (HDR-6, HDR-12)",
        "vocab = [] with blank_id 0 (no index is in 0 ... V-1)", None, failing_check="NTS-BLANK",
        writer=_w_lines([dict(h0, blank_id=0), *hyp0, {"type": "end"}]))
    # --- NTS 1.0 RC3 (VER-6 ... VER-10): unknown enumeration values
    h11 = _header(spec_version="1.1", vocab_type="syllable", clock_domain="gps",
                  meta={**BASE_META, "device.modality": "ultrasound"})
    unk = [{"type": "signal_quality", "t": 0.0, "value": 512.0, "unit": "lux"},
           {"type": "decision", "t": 0.04, "label": "a", "score": 3.5, "score_semantics": "logit_margin"},
           {"type": "pointer", "t": 0.04, "dims": 2, "mode": "polar", "values": [0.3, 1.2]}]
    add("V66", "v66-unknown-enums-v1-1.jsonl", "accept", "1.0 RC3 11.2.1 (VER-8)",
        'Header spec_version "1.1" with unknown enumeration values (vocab_type, clock_domain, device.modality, '
        "signal_quality unit, decision score_semantics, pointer mode): accepted, kept as unknown", None,
        {"n_frames": 2, "vocab_type": "syllable", "events": 3},
        writer=_w_lines([h11, *_frames(2, V), *unk, {"type": "end"}]))
    add("V67", "v67-unknown-clock-v1-0.jsonl", "reject", "1.0 RC3 11.2.1 (VER-7) / 5.3 (HDR-11)",
        'Header spec_version "1.0" with clock_domain "gps": 1.0 data must use the values of 1.0', None,
        failing_check="NTS-CLOCK", writer=_w_lines([_header(spec_version="1.0", clock_domain="gps"), *_frames(2, V)]))
    add("V68", "v68-vocab-type-number-v1-1.jsonl", "reject", "1.0 RC3 11.2.1 (VER-8) / 3.1 (HDR-5)",
        'Header spec_version "1.1" with vocab_type 5: an unknown value must still be a string', None,
        failing_check="NTS-VOCAB-TYPE", writer=_w_lines([_header(spec_version="1.1", vocab_type=5), *_frames(2, V)]))
    # --- NTS 1.0 RC4 (gap G-12, FEP-0008): optional fields have their types (GEN-11)
    timed = [dict(f, t_signal_start=round(f["t"] - 0.2, 6), t_signal_end=f["t"], t_decoded=round(f["t"] + 0.01, 6),
                  t_emitted=round(f["t"] + 0.02, 6)) for f in _frames(2, V)]
    opt = [{"type": "signal_quality", "t": 0.04, "value": 0.92, "unit": "index", "channels": [0.9, 0.95, 0.91]},
           {"type": "decision", "t": 0.08, "label": "a", "score": 0.71, "score_semantics": "calibrated_prob",
            "score_range": [0.0, 1.0]},
           {"type": "hypothesis", "id": "h1", "is_final": True, "score_semantics": "none", "revision_of": None,
            "t_start": 0.0, "t_end": 0.08,
            "nbest": [{"text": "ab", "score": -1.2, "spans": [{"char_start": 0, "char_end": 1, "t_start": 0.0, "t_end": 0.04,
                                                              "score": -0.5}, {"char_start": 1, "char_end": 2}]}]},
           {"type": "pointer", "t": 0.08, "dims": 2, "mode": "absolute", "values": [0.5, 0.25], "absent": [False, False],
            "score": 0.8, "score_semantics": "uncalibrated_prob"}]
    hopt = _header(spec_version="1.0", vocab_id="char.b2q-28", vocab_version="1", meta={**BASE_META, "emg.gain_db": 20.0})
    add("V69", "v69-optional-field-types.jsonl", "accept", "1.0 RC4 4.1 (GEN-11) / 3.4 (MET-3)",
        "Optional fields with their types: header vocab_id and vocab_version, latency fields on frames, signal_quality "
        "channels, decision score_range with a probability, hypothesis t_start, t_end, revision_of null and spans, pointer "
        "absent, score and score_semantics; a custom meta key in the planned namespace emg (a warning only, MET-3)",
        None, {"n_frames": 2, "events": 4}, writer=_w_lines([hopt, *timed, *opt, {"type": "end"}]))

    def _ev(i: int, **kw: Any) -> list[dict[str, Any]]:
        e = {k: v for k, v in dict(opt[i], **kw).items() if v is not _DROP}
        return [_header(spec_version="1.0"), *_frames(2, V), e, {"type": "end"}]

    sp_bad = [{"text": "ab", "score": -1.2, "spans": [{"char_start": -1, "char_end": 1}]}]
    for vid, fname, clause, desc, chk, lines in (
            ("V70", "v70-hyp-t-start-string.jsonl", "4.7 (HYP-5)", 'hypothesis t_start is the string "0.0"',
             "NTS-EVT-HYPOTHESIS", _ev(2, t_start="0.0")),
            ("V71", "v71-hyp-span-negative.jsonl", "4.7 (HYP-5)", "hypothesis n-best span with char_start -1",
             "NTS-EVT-HYPOTHESIS", _ev(2, nbest=sp_bad)),
            ("V72", "v72-hyp-revision-of-number.jsonl", "4.7 (HYP-5)", "hypothesis revision_of is the number 3",
             "NTS-EVT-HYPOTHESIS", _ev(2, revision_of=3)),
            ("V73", "v73-sq-channels-strings.jsonl", "4.5 (SQ-1)", 'signal_quality channels is ["good", "bad"]',
             "NTS-EVT-SIGNAL-QUALITY", _ev(0, channels=["good", "bad"])),
            ("V74", "v74-pointer-bad-semantics.jsonl", "4.8 (PTR-1) / 4.6",
             'pointer score_semantics "probability" (not a 1.0 value)', "NTS-EVT-POINTER",
             _ev(3, score_semantics="probability")),
            ("V75", "v75-pointer-absent-length.jsonl", "4.8 (PTR-1)", "pointer with dims 2 and absent [true] (one value)",
             "NTS-EVT-POINTER", _ev(3, absent=[True])),
            ("V76", "v76-decision-range-string.jsonl", "4.6 (DEC-6)",
             'decision with calibrated_prob and score_range "0-1" (not two numbers)', "NTS-EVT-DECISION",
             _ev(1, score_range="0-1")),
            ("V77", "v77-decision-score-string.jsonl", "4.6 (DEC-6)",
             'decision with power, score_range [0, 10] and score "high"', "NTS-EVT-DECISION",
             _ev(1, score="high", score_semantics="power", score_range=[0, 10])),
            ("V79", "v79-frame-t-emitted-string.jsonl", "5.2 (TIM-4)", 'a frame with t_emitted "late"',
             "NTS-EVT-TIMING", [_header(spec_version="1.0"), timed[0], dict(timed[1], t_emitted="late"), {"type": "end"}]),
            ("V80", "v80-frame-timing-order.jsonl", "5.2 (TIM-4)", "a frame with t_decoded after t_emitted",
             "NTS-EVT-TIMING", [_header(spec_version="1.0"), timed[0], dict(timed[1], t_decoded=1.0), {"type": "end"}])):
        add(vid, fname, "reject", "1.0 RC4 " + clause, desc, None, failing_check=chk, writer=_w_lines(lines))
    add("V81", "v81-decision-score-string-v1-1.jsonl", "reject", "1.0 RC4 4.6 (DEC-6) / 11.2.1 (VER-8)",
        'Header spec_version "1.1": a decision with the unknown score_semantics "logit_margin" and score "high" '
        "(an unknown semantics keeps the type rules)", None, failing_check="NTS-EVT-DECISION",
        writer=_w_lines([_header(spec_version="1.1"), *_frames(2, V),
                         {"type": "decision", "t": 0.04, "label": "a", "score": "high", "score_semantics": "logit_margin"},
                         {"type": "end"}]))
    add("V82", "v82-pointer-semantics-null.jsonl", "reject", "1.0 RC4 4.8 (PTR-1) / 4.1 (GEN-9)",
        "pointer score_semantics is null (the field type has no null)", None, failing_check="NTS-EVT-POINTER",
        writer=_w_lines(_ev(3, score=_DROP, score_semantics=None)))
    add("V78", "v78-header-vocab-id-number.jsonl", "reject", "1.0 RC4 3.1 (HDR-16)", "header vocab_id is the number 28",
        None, failing_check="NTS-VOCAB-ID", writer=_w_lines([_header(spec_version="1.0", vocab_id=28), *_frames(2, V)]))
    # --- NTS 1.0 RC4 amendment (FEP-0009): modality keys emg.*, meg.*, implant.* (MET-11)
    mod_implant = {**BASE_META, "device.modality": "intracortical", "device.invasive": True,
                   "implant.array_type": "utah", "implant.array_count": 2,
                   "implant.features": ["threshold_crossings", "spike_band_power"], "implant.bin_s": 0.02,
                   "implant.areas": ["precentral gyrus"]}
    mod_emg = {**BASE_META, "device.modality": "emg", "device.invasive": False, "emg.placement": "wrist",
               "emg.derivation": "bipolar"}
    mod_meg = {**BASE_META, "device.modality": "meg", "device.invasive": False,
               "meg.sensor_types": ["magnetometer", "planar_gradiometer"]}
    for vid, fname, desc, meta in (
            ("V83", "v83-modality-keys-implant.jsonl", "Implant modality keys with their types: implant.array_type, "
             "array_count, features, bin_s and areas", mod_implant),
            ("V84", "v84-modality-keys-emg.jsonl", "EMG modality keys with their types: emg.placement and emg.derivation",
             mod_emg),
            ("V85", "v85-modality-keys-meg.jsonl", "MEG modality key with its type: meg.sensor_types", mod_meg)):
        add(vid, fname, "accept", "1.0 RC4 3.4 (MET-1, MET-11; FEP-0009)", desc, None, {"n_frames": 2},
            writer=_w_lines([_header(spec_version="1.0", meta=meta), *_frames(2, V), {"type": "end"}]))
    add("V86", "v86-implant-bin-s-string.npz", "reject", "1.0 RC4 3.4 (MET-1; FEP-0009)",
        'implant.bin_s is the string "0.02" (type number >= 0)', None, failing_check="NTS-META-TYPES",
        writer=_w_npz(meta_json=np.array(json.dumps(mod_implant | {"implant.bin_s": "0.02"}))))
    add("V87", "v87-meg-sensor-types-empty-item.npz", "reject", "1.0 RC4 3.4 (MET-1, MET-7; FEP-0009)",
        'meg.sensor_types has an empty string item (type list of non-empty strings)', None,
        failing_check="NTS-META-TYPES",
        writer=_w_npz(meta_json=np.array(json.dumps(mod_meg | {"meg.sensor_types": ["magnetometer", ""]}))))
    # --- NTS 1.0 RC4 amendment (gap G-13 a, option A2): a dense frame with sparse keys (FRM-2, GEN-11)
    both = _frames(2, V)
    extra = {"top_ids": [0, 1], "top_log_probs": [round(math.log(0.6), 6), None], "rest_log_prob": -0.5}
    add("V88", "v88-dense-frame-sparse-keys.jsonl", "accept", "1.0 RC4 4.2 (FRM-2, GEN-11)",
        "A dense frame that also carries well-typed sparse keys (not normalised): the dense form wins", None,
        {"n_frames": 2}, writer=_w_lines([_header(spec_version="1.0"), both[0], both[1] | extra, {"type": "end"}]))
    for vid, fname, desc, keys in (
            ("V89", "v89-dense-frame-top-ids-string.jsonl", 'a dense frame with top_ids "0,1" (not a list)',
             {"top_ids": "0,1"}),
            ("V90", "v90-dense-frame-top-log-probs-string.jsonl", 'a dense frame with top_log_probs [-0.5, "x"]',
             {"top_ids": [0, 1], "top_log_probs": [-0.5, "x"]}),
            ("V91", "v91-dense-frame-rest-string.jsonl", 'a dense frame with rest_log_prob "-inf" (a string)',
             {"rest_log_prob": "-inf"}),
            ("V92", "v92-dense-frame-top-ids-repeated.jsonl", "a dense frame with top_ids [1, 1] (not unique)",
             {"top_ids": [1, 1], "top_log_probs": [-1.0, -1.0]})):
        add(vid, fname, "reject", "1.0 RC4 4.2 (FRM-2, GEN-11)", desc, None, failing_check="NTS-JSONL-FRAME",
            writer=_w_lines([_header(spec_version="1.0"), both[0], both[1] | keys, {"type": "end"}]))
    # --- NTS 1.0 RC4 amendment 3 (roadmap P1-16, gap 20): the advisory modality match of MET-11.
    # Accept vectors: a mismatch is a warning (NTS-MODALITY-MATCH), never a reject. "expected" pins the warnings,
    # so the three SDKs must report the same advisory checks.
    mm = "1.0 RC4 3.4 (MET-11; amendment 3)"
    add("V93", "v93-modality-mismatch-emg-on-eeg.jsonl", "accept", mm,
        "EMG keys (emg.placement, emg.derivation) on a stream with device.modality eeg: accepted with the MET-11 warning",
        None, {"n_frames": 2, "warnings": ["NTS-MODALITY-MATCH"]},
        writer=_w_lines([_header(spec_version="1.0", meta={**mod_emg, "device.modality": "eeg"}), *_frames(2, V),
                         {"type": "end"}]))
    add("V94", "v94-modality-mismatch-implant-on-meg.npz", "accept", mm,
        "implant.* keys on an NPZ stream with device.modality meg: accepted with the MET-11 warning", None,
        {"warnings": ["NTS-MODALITY-MATCH"]},
        writer=_w_npz(meta_json=np.array(json.dumps(mod_implant | {"device.modality": "meg", "device.invasive": False}))))
    add("V95", "v95-modality-match-opm-meg.jsonl", "accept", mm,
        "meg.sensor_types on a stream with device.modality opm-meg (meg.* goes with meg and opm-meg): no warning", None,
        {"n_frames": 2, "warnings": []},
        writer=_w_lines([_header(spec_version="1.0", meta={**mod_meg, "device.modality": "opm-meg"}), *_frames(2, V),
                         {"type": "end"}]))
    add("V96", "v96-modality-keys-other.jsonl", "accept", mm,
        "emg.placement and implant.areas on a stream with device.modality other: accepted with the MET-11 warning", None,
        {"n_frames": 2, "warnings": ["NTS-MODALITY-MATCH"]},
        writer=_w_lines([_header(spec_version="1.0", meta={**BASE_META, "device.modality": "other",
                                                            "emg.placement": "forearm", "implant.areas": ["M1"]}),
                         *_frames(2, V), {"type": "end"}]))
    # --- P14-17 (gap 42): TD-4. A trust_decision is trust layer output; it MUST NOT be in an input stream. Before
    # P14-17 the v0.1 suite ignored it as an unknown event type (6.2 rule 5); only the fep-0001 profile caught it.
    add("V97", "v97-trust-decision-in-input.jsonl", "reject", "1.0 RC4 6.1 (TD-4)",
        "A trust_decision event inside an input stream (it belongs in a decision log)", None,
        failing_check="NTS-TD-INPUT",
        writer=_w_lines([_header(spec_version="1.0"), *_frames(2, V),
                         {"type": "trust_decision", "spec_version": "1.0", "session": "u1", "seq": 0, "utterance": 0,
                          "is_final": True, "action": "COMMIT", "p_top1": 0.93, "score_semantics": "calibrated_prob",
                          "shown": ["ab"]}, {"type": "end"}]))
    # --- NTS 1.0 RC4 amendment 6 (FEP-0010, roadmap P5-13): the data licence keys data.licence and
    # data.research_only (MET-12). The validators check the types; MET-12 (research_only true for an NC licence) is
    # content and not checked.
    lic = {**BASE_META, "data.licence": "CC-BY-NC-4.0", "data.research_only": True}
    add("V98", "v98-data-licence-keys.jsonl", "accept", "1.0 RC4 3.4 (MET-1, MET-12; FEP-0010)",
        'Data licence keys with their types: data.licence "CC-BY-NC-4.0" and data.research_only true', None,
        {"n_frames": 2, "warnings": []},
        writer=_w_lines([_header(spec_version="1.0", meta=lic), *_frames(2, V), {"type": "end"}]))
    add("V99", "v99-data-licence-empty.jsonl", "reject", "1.0 RC4 3.4 (MET-1, MET-7; FEP-0010)",
        'data.licence is "" (type non-empty string)', None, failing_check="NTS-META-TYPES",
        writer=_w_lines([_header(spec_version="1.0", meta=lic | {"data.licence": ""}), *_frames(2, V),
                         {"type": "end"}]))
    add("V100", "v100-data-research-only-string.npz", "reject", "1.0 RC4 3.4 (MET-1; FEP-0010)",
        'data.research_only is the string "yes" (type boolean)', None, failing_check="NTS-META-TYPES",
        writer=_w_npz(meta_json=np.array(json.dumps(lic | {"data.research_only": "yes"}))))
    vs.sort(key=lambda v: (len(v.vid), v.vid))  # V100 after V99
    return vs


def write_vectors(out_dir: str | PathLike[str]) -> dict[str, Any]:
    """Write all vectors and ``manifest.json`` to ``out_dir``. Returns the manifest."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    vectors = build_vectors()
    for v in vectors:
        assert v.writer is not None
        v.writer(out / v.file)
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "spec_version": "0.1",
        "generator": "python -m fidetype.conformance vectors",
        "how_to_use": ("For each vector, load the file with your consumer. A conforming consumer accepts exactly the "
                       "vectors with expect = accept and rejects the others. For accepted files, check the values in "
                       "'expected'. 'failing_check' names the suite check that the file breaks."),
        "vectors": [v.to_manifest() for v in vectors],
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return manifest


def default_vectors_dir() -> Path:
    """``spec/conformance/v0.1`` of the repository (checkout), else the copy in the installed wheel."""
    repo = Path(__file__).resolve().parents[3] / "spec" / "conformance" / "v0.1"
    if repo.is_dir():
        return repo
    # The wheel ships spec/conformance as fidetype/_spec/conformance (pyproject force-include).
    return Path(__file__).resolve().parents[1] / "_spec" / "conformance" / "v0.1"


# --- consumer conformance -------------------------------------------------------------------


@dataclass
class ConsumerOutcome:
    vid: str
    expect: str
    actual: str
    ok: bool
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.vid, "expect": self.expect, "actual": self.actual, "ok": self.ok, "detail": self.detail}


def _summary_of(obj: Any) -> dict[str, Any]:
    """Read comparable values from a consumer result (ConsumedStream, NeuralTextStream or dict)."""
    from fidetype.conformance.io import ConsumedStream

    if isinstance(obj, ConsumedStream):
        s = obj.stream
        return {"n_frames": s.n_frames, "vocab_size": s.vocab_size, "vocab_type": s.vocab_type, "blank_id": s.blank_id,
                "neg_inf_cells": int(np.isneginf(s.log_probs).sum()), "ignored_events": obj.ignored_events,
                "unknown_keys": obj.unknown_keys, "vocab_type_defaulted": obj.vocab_type_defaulted,
                "events": len(obj.events), "warnings": obj.warnings, "level": obj.level}
    if isinstance(obj, NeuralTextStream):
        return {"n_frames": obj.n_frames, "vocab_size": obj.vocab_size, "vocab_type": obj.vocab_type,
                "blank_id": obj.blank_id, "neg_inf_cells": int(np.isneginf(obj.log_probs).sum())}
    if isinstance(obj, dict):
        return obj
    return {}


def run_consumer(consume: Callable[[Path], Any], vectors_dir: str | PathLike[str] | None = None) -> list[ConsumerOutcome]:
    """Run a consumer over the golden vectors.

    ``consume(path)`` must return a value (accept) or raise an exception
    (reject). If it returns a :class:`~fidetype.conformance.io.ConsumedStream`,
    a :class:`NeuralTextStream` or a dict, the ``expected`` values of the
    manifest are compared with the keys it provides.
    """
    vdir = Path(vectors_dir) if vectors_dir is not None else default_vectors_dir()
    manifest = json.loads((vdir / "manifest.json").read_text(encoding="utf-8"))
    out = []
    for v in manifest["vectors"]:
        try:
            res = consume(vdir / v["file"])
            actual, detail = "accept", ""
        except Exception as e:  # noqa: BLE001 - any exception is a rejection
            res, actual, detail = None, "reject", f"{type(e).__name__}: {e}"
        ok = actual == v["expect"]
        if ok and actual == "accept" and v.get("expected"):
            got = _summary_of(res)
            diffs = [f"{k}: expected {want!r}, got {got[k]!r}" for k, want in v["expected"].items()
                     if k in got and got[k] != want]
            if diffs:
                ok, detail = False, "; ".join(diffs)
        out.append(ConsumerOutcome(v["id"], v["expect"], actual, ok, detail[:300]))
    return out


def command_consumer(cmd: str, timeout: float = 60.0) -> Callable[[Path], Any]:
    """A consumer that runs an external program: ``cmd`` with ``{path}`` replaced.

    Exit code 0 means accept; any other exit code means reject. If the
    program prints a JSON object on stdout, its keys (``n_frames``,
    ``vocab_type``, ``blank_id``, ...) are compared with the manifest.
    This lets implementations in any language run the suite.
    """
    def consume(path: Path) -> Any:
        args = [a.replace("{path}", str(path)) for a in shlex.split(cmd, posix=True)]
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        if p.returncode != 0:
            raise RuntimeError(f"exit {p.returncode}: {p.stderr.strip()[:200]}")
        try:
            obj = json.loads(p.stdout)
            return obj if isinstance(obj, dict) else {}
        except ValueError:
            return {}

    return consume
