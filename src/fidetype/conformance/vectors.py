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
    vs.sort(key=lambda v: v.vid)
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
    """``spec/conformance/v0.1`` of the repository (if the package runs from a checkout)."""
    return Path(__file__).resolve().parents[3] / "spec" / "conformance" / "v0.1"


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
                "events": len(obj.events)}
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
