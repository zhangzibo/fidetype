"""The checks of the NeuralTextStream v0.1 conformance suite.

Each check tests one rule. Each check cites the spec clause that it comes
from (``spec/neuraltextstream-v0.1.md``) and has one **level**:

``core``
    The MUST rules of the frame core and of the serialisations (3.1-3.3,
    4.1, 4.2 types, 5.1, 5.2, 6.1, 6.2) and the MUST rules of the
    Development event kinds (3.5-3.9). A consumer MUST reject a stream
    that fails a core check. Heuristic core checks (leakage 5.3, privacy
    5.4) look only for clear signs; they cannot prove absence.
``trust-ready``
    The SHOULD rules and profile requirements that a trust layer needs
    to use the stream safely: who made it, what the device is, whether
    the decoder is causal, whether a calibration step already ran.
``provenance``
    The recommendations of section 4.3: the stream can be traced to the
    decoder weights, the adapter and a stream id.
``advisory``
    Good practice. A failed advisory check is a warning. It never
    blocks a level.

Keywords: ``MUST`` and ``SHOULD`` copy the spec text. ``PROFILE`` marks a
requirement that this suite adds for a level; its clause names the spec
text that motivates it. ``heuristic`` marks a check that can miss
problems.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

import numpy as np

from fidetype.conformance.io import RawStream, _MissingMeta
from fidetype.streams.spec import NORM_TOL, SPEC_VERSION, VOCAB_TYPES
from fidetype.streams.vocab import VOCAB as CHAR_B2Q_28

LEVELS = ("core", "trust-ready", "provenance")
LEVEL_ORDER = {name: i for i, name in enumerate(LEVELS)}
ADVISORY = "advisory"

PASS, FAIL, SKIP = "pass", "fail", "skip"


@dataclass(frozen=True)
class Check:
    check_id: str
    level: str  # core | trust-ready | provenance | advisory
    keyword: str  # MUST | SHOULD | PROFILE
    clause: str
    title: str
    fn: Callable[[RawStream], tuple[str, str]]
    heuristic: bool = False
    formats: tuple[str, ...] = ("npz", "jsonl", "object")


@dataclass
class CheckResult:
    check_id: str
    level: str
    keyword: str
    clause: str
    title: str
    status: str
    message: str = ""
    heuristic: bool = False

    def blocks(self, level: str) -> bool:
        """True if a failure of this check blocks ``level``."""
        if self.level == ADVISORY:
            return False
        return LEVEL_ORDER[self.level] <= LEVEL_ORDER[level]

    @property
    def outcome(self) -> str:
        """``pass``, ``fail``, ``warn`` (a failed advisory check) or ``skip``."""
        if self.status == FAIL and self.level == ADVISORY:
            return "warn"
        return self.status

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.check_id, "level": self.level, "keyword": self.keyword, "clause": self.clause,
            "title": self.title, "outcome": self.outcome, "message": self.message, "heuristic": self.heuristic,
        }


REGISTRY: list[Check] = []


def check(check_id: str, level: str, keyword: str, clause: str, title: str, *, heuristic: bool = False,
          formats: tuple[str, ...] = ("npz", "jsonl", "object")) -> Callable:
    def deco(fn: Callable[[RawStream], tuple[str, str]]) -> Callable:
        REGISTRY.append(Check(check_id, level, keyword, clause, title, fn, heuristic, formats))
        return fn

    return deco


def ok(msg: str = "") -> tuple[str, str]:
    return PASS, msg


def bad(msg: str) -> tuple[str, str]:
    return FAIL, msg


def skip(msg: str) -> tuple[str, str]:
    return SKIP, msg


# --- helpers ------------------------------------------------------------------------


def _is_int(x: Any) -> bool:
    return isinstance(x, (int, np.integer)) and not isinstance(x, (bool, np.bool_))


def _is_num(x: Any) -> bool:
    return isinstance(x, (int, float, np.integer, np.floating)) and not isinstance(x, (bool, np.bool_))


def _vocab(raw: RawStream) -> list | None:
    v = raw.get("vocab")
    return v if isinstance(v, list) else None


def _meta(raw: RawStream) -> dict | None:
    m = raw.header.get("meta")
    return m if isinstance(m, dict) else None


def _lp(raw: RawStream) -> np.ndarray | None:
    lp = raw.log_probs
    return lp if lp is not None and lp.ndim == 2 else None


def _walk(obj: Any, prefix: str = "") -> Iterable[tuple[str, Any]]:
    """Yield (dotted key path, value) for every leaf in a JSON value."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{prefix}.{k}" if prefix else str(k)
            yield p, v
            yield from _walk(v, p)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk(v, f"{prefix}[{i}]")


# --- defined meta keys (spec 4.2) ----------------------------------------------------------

MODALITIES = ("emg", "eeg", "meg", "opm-meg", "ecog", "intracortical", "fnirs", "other")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_BCP47_RE = re.compile(r"^[A-Za-z]{2,8}(-[A-Za-z0-9]{1,8})*$")


def _t_str(v: Any) -> str | None:
    return None if isinstance(v, str) and v != "" else "a non-empty string"


def _t_bool(v: Any) -> str | None:
    return None if isinstance(v, bool) else "a boolean"


def _t_enum(values: tuple[str, ...]) -> Callable[[Any], str | None]:
    return lambda v: None if v in values else f"one of {list(values)}"


def _t_int_ge1(v: Any) -> str | None:
    return None if _is_int(v) and v >= 1 else "an integer >= 1"


def _t_nonneg(v: Any) -> str | None:
    return None if _is_num(v) and math.isfinite(v) and v >= 0 else "a finite number >= 0"


def _t_sha(v: Any) -> str | None:
    return None if isinstance(v, str) and _SHA256_RE.match(v) else "64 lowercase hex characters (SHA-256)"


def _t_lang(v: Any) -> str | None:
    return None if isinstance(v, str) and _BCP47_RE.match(v) else "a BCP 47 language tag"


DEFINED_KEYS: dict[str, Callable[[Any], str | None]] = {
    "device.modality": _t_enum(MODALITIES),
    "device.vendor": _t_str,
    "device.model": _t_str,
    "device.channel_count": _t_int_ge1,
    "device.invasive": _t_bool,
    "device.regulatory_status": _t_str,
    "decoder.name": _t_str,
    "decoder.version": _t_str,
    "decoder.causal": _t_bool,
    "decoder.lookahead_s": _t_nonneg,
    "decoder.calibration_id": _t_str,
    "decoder.calibration_method": _t_str,
    "decoder.weights_sha256": _t_sha,
    "adapter.name": _t_str,
    "adapter.version": _t_str,
    "stream.id": _t_str,
    "lm.name": _t_str,
    "user.personalized": _t_bool,
    "session.id": _t_str,
    "subject.id": _t_str,
    "language": _t_lang,
    "calibration.applied": _t_bool,
    "data.derived": _t_bool,
    "consent.ref": _t_str,
}
DEFINED_NAMESPACES = tuple(sorted({k.split(".")[0] for k in DEFINED_KEYS if "." in k}))

#: Known registered vocabularies (spec 3.4). Only one entry is defined in v0.1.
KNOWN_VOCAB_IDS: dict[str, tuple[str, ...]] = {"char.b2q-28": tuple(CHAR_B2Q_28)}

# Key names (last path segment, lower case) that suggest ground truth (5.3).
LEAK_KEY_NAMES = {
    "target_text", "typed_text", "truth", "ground_truth", "groundtruth", "label", "labels", "transcript",
    "transcription", "cue_sentence", "cue_text", "sentence", "reference_text", "target", "answer",
    "true_text", "gold",
}
# Key names that suggest personal identifiers (5.4.1).
PII_KEY_NAMES = {
    "name", "full_name", "first_name", "last_name", "email", "e_mail", "dob", "date_of_birth", "birthdate",
    "birth_date", "address", "phone", "phone_number", "mrn", "medical_record_number", "ssn",
}
_PERSON_NS = {"subject", "participant", "user", "patient", "person", "operator"}
FREE_TEXT_KEY_NAMES ={"note", "notes", "comment", "comments", "remarks", "description"}
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PSEUDO_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$")

ARPABET = frozenset(
    "AA AE AH AO AW AY B CH D DH EH ER EY F G HH IH IY JH K L M N NG OW OY P R S SH T TH UH UW V W Y Z ZH".split()
)
PHONEME_MARKERS = frozenset({"SIL", "SP", "sil", "sp", "|", "<sil>", "<sp>"})
_W3C_CODE_RE = re.compile(
    r"^(Key[A-Z]|Digit[0-9]|Numpad\w+|F[0-9]{1,2}|Arrow(Up|Down|Left|Right)|Space|Enter|Backspace|Tab|Escape|"
    r"(Shift|Control|Alt|Meta)(Left|Right)|CapsLock|Minus|Equal|BracketLeft|BracketRight|Backslash|Semicolon|"
    r"Quote|Backquote|Comma|Period|Slash|Delete|Home|End|PageUp|PageDown|Insert|IntlBackslash|ContextMenu)$"
)

SCORE_SEMANTICS = ("calibrated_prob", "uncalibrated_prob", "power", "strength", "none")
CLOCK_DOMAINS = ("lsl", "unix", "monotonic", "trial", "other")
SQ_UNITS = ("index", "snr_db", "impedance_ohm", "other")


def _issue_check(check_id: str) -> Callable[[RawStream], tuple[str, str] | None]:
    def f(raw: RawStream) -> tuple[str, str] | None:
        msgs = [i.message for i in raw.issues if i.check_id == check_id]
        return bad("; ".join(msgs)) if msgs else None

    return f


# --- parse and serialisation (6.1, 6.2) -------------------------------------------------------


@check("NTS-PARSE", "core", "MUST", "6.1 / 6.2", "The file loads in its serialisation (NPZ without pickle; UTF-8 JSON Lines)")
def c_parse(raw: RawStream) -> tuple[str, str]:
    r = _issue_check("NTS-PARSE")(raw)
    if r:
        return r
    return ok() if raw.format != "object" else skip("in-memory stream")


@check("NTS-NPZ-KEYS", "core", "MUST", "6.1", "The NPZ file has all required keys", formats=("npz",))
def c_npz_keys(raw: RawStream) -> tuple[str, str]:
    return _issue_check("NTS-NPZ-KEYS")(raw) or ok()


@check("NTS-NPZ-DTYPE", ADVISORY, "SHOULD", "6.1", "NPZ dtypes follow the 6.1 table (log_probs float32, frame_times float64, blank_id int64)",
       formats=("npz",))
def c_npz_dtype(raw: RawStream) -> tuple[str, str]:
    want = {"log_probs": "float32", "frame_times": "float64", "blank_id": "int64", "frame_period": "float64",
            "latency": "float64"}
    diffs = [f"{k} is {raw.npz_dtypes[k]}, table says {d}" for k, d in want.items()
             if k in raw.npz_dtypes and raw.npz_dtypes[k] != d]
    return bad("; ".join(diffs)) if diffs else ok()


@check("NTS-UNKNOWN-KEYS", ADVISORY, "MUST", "6.1 note / 6.2.5", "Unknown keys are reported; a consumer MUST ignore them")
def c_unknown(raw: RawStream) -> tuple[str, str]:
    if raw.unknown_keys:
        return ok(f"unknown keys (a consumer ignores them): {raw.unknown_keys}")
    return ok()


@check("NTS-JSONL-HEADER", "core", "MUST", "6.2.1", "Line 1 is the header with type, spec_version, vocab, vocab_type, blank_id",
       formats=("jsonl",))
def c_jsonl_header(raw: RawStream) -> tuple[str, str]:
    return _issue_check("NTS-JSONL-HEADER")(raw) or ok()


@check("NTS-JSONL-FRAME", "core", "MUST", "6.2.2 / 6.2.3", "Each frame has t and log_probs (numbers or null) or the sparse keys",
       formats=("jsonl",))
def c_jsonl_frame(raw: RawStream) -> tuple[str, str]:
    return _issue_check("NTS-JSONL-FRAME")(raw) or ok()


@check("NTS-JSONL-END", ADVISORY, "SHOULD", "6.2", "No lines after the end marker", formats=("jsonl",))
def c_jsonl_end(raw: RawStream) -> tuple[str, str]:
    if raw.lines_after_end:
        return bad(f"{raw.lines_after_end} line(s) after the end marker (ignored; see ambiguity A5)")
    return ok("end marker present" if raw.has_end else "no end marker (allowed, 6.2.6)")


# --- frame core structure (3.1, 5.1) -----------------------------------------------------------


@check("NTS-VERSION", "core", "MUST", "5.1.4", 'spec_version is a version the consumer supports ("0.1")')
def c_version(raw: RawStream) -> tuple[str, str]:
    if "spec_version" not in raw.header:
        return skip("no spec_version (reported by the serialisation check)")
    v = raw.header["spec_version"]
    return ok() if v == SPEC_VERSION else bad(f"spec_version {v!r} is not supported (this suite supports {SPEC_VERSION!r})")


@check("NTS-LP-2D", "core", "MUST", "5.1.1", "log_probs has exactly 2 dimensions [T, V]")
def c_lp_2d(raw: RawStream) -> tuple[str, str]:
    r = _issue_check("NTS-LP-2D")(raw)
    if r:
        return r
    if raw.log_probs is None:
        return skip("no log_probs")
    return ok() if raw.log_probs.ndim == 2 else bad(f"log_probs has shape {raw.log_probs.shape}")


@check("NTS-V-MATCH", "core", "MUST", "5.1.2", "V equals the length of vocab")
def c_v_match(raw: RawStream) -> tuple[str, str]:
    r = _issue_check("NTS-V-MATCH")(raw)
    if r:
        return r
    lp, v = _lp(raw), _vocab(raw)
    if lp is None or v is None:
        return skip("no 2-D log_probs or no vocab list")
    return ok() if lp.shape[1] == len(v) else bad(f"log_probs has {lp.shape[1]} columns, vocab has {len(v)} tokens")


@check("NTS-FT-SHAPE", "core", "MUST", "5.1.3", "frame_times has shape [T]")
def c_ft_shape(raw: RawStream) -> tuple[str, str]:
    r = _issue_check("NTS-FT-SHAPE")(raw)
    if r:
        return r
    lp, ft = _lp(raw), raw.frame_times
    if lp is None or ft is None:
        return skip("no log_probs or frame_times")
    return ok() if ft.shape == (lp.shape[0],) else bad(f"frame_times has shape {ft.shape}, expected ({lp.shape[0]},)")


@check("NTS-VOCAB-TYPE", "core", "MUST", "5.1.5", "vocab_type is one of char, key, word, phoneme, command, other")
def c_vocab_type(raw: RawStream) -> tuple[str, str]:
    vt = raw.header.get("vocab_type")
    if vt is None and "vocab_type" not in raw.header:
        return skip("no vocab_type (reported by the serialisation check)")
    return ok() if vt in VOCAB_TYPES else bad(f"vocab_type {vt!r} is not one of {list(VOCAB_TYPES)}")


@check("NTS-VOCAB-STR", "core", "MUST", "3.1", "vocab is a list of strings")
def c_vocab_str(raw: RawStream) -> tuple[str, str]:
    if "vocab" not in raw.header:
        return skip("no vocab")
    v = raw.header["vocab"]
    if not isinstance(v, list):
        return bad(f"vocab is not a list ({type(v).__name__})")
    bad_items = [i for i, t in enumerate(v) if not isinstance(t, str)]
    return bad(f"vocab items {bad_items[:5]} are not strings") if bad_items else ok()


@check("NTS-VOCAB-UNIQUE", "core", "MUST", "5.2.4", "vocab tokens are unique")
def c_vocab_unique(raw: RawStream) -> tuple[str, str]:
    v = _vocab(raw)
    if v is None:
        return skip("no vocab list")
    seen, dup = set(), []
    for t in v:
        k = json.dumps(t) if not isinstance(t, str) else t
        if k in seen:
            dup.append(t)
        seen.add(k)
    return bad(f"duplicate tokens {dup[:5]}") if dup else ok()


@check("NTS-BLANK", "core", "MUST", "3.1 / 5.1.6", "blank_id is null or an integer in 0..V-1")
def c_blank(raw: RawStream) -> tuple[str, str]:
    if "blank_id" not in raw.header:
        return skip("no blank_id (reported by the serialisation check)")
    b = raw.header["blank_id"]
    if b is None:
        return ok("no blank (not a CTC decoder)")
    if not _is_int(b):
        return bad(f"blank_id {b!r} is not an integer or null")
    v = _vocab(raw)
    if v is None:
        return skip("no vocab list")
    return ok() if 0 <= b < len(v) else bad(f"blank_id {b} is out of range 0..{len(v) - 1}")


@check("NTS-SOURCE", "core", "MUST", "5.1.7", "source, if present, is a non-empty string")
def c_source(raw: RawStream) -> tuple[str, str]:
    if "source" not in raw.header:
        return ok("absent (default \"unknown\")")
    s = raw.header["source"]
    return ok() if isinstance(s, str) and s else bad(f"source {s!r} is not a non-empty string")


@check("NTS-META-OBJECT", "core", "MUST", "5.1.7", "meta, if present, is a JSON object")
def c_meta_obj(raw: RawStream) -> tuple[str, str]:
    m = raw.header.get("meta", {})
    if isinstance(m, _MissingMeta):
        return skip("meta is not parseable (reported by NTS-META-JSON)")
    return ok() if isinstance(m, dict) else bad(f"meta is a {type(m).__name__}, not an object")


@check("NTS-META-JSON", "core", "MUST", "4.1", "meta values are JSON values (no NaN, no infinity, no other types)")
def c_meta_json(raw: RawStream) -> tuple[str, str]:
    r = _issue_check("NTS-META-JSON")(raw)
    if r:
        return r
    m = raw.header.get("meta", {})
    try:
        json.dumps(m, allow_nan=False)
    except (TypeError, ValueError) as e:
        return bad(f"meta is not pure JSON: {e}")
    return ok()


# --- values (5.2) ---------------------------------------------------------------------------


@check("NTS-LP-FINITE", "core", "MUST", "5.2.2", "log_probs has no NaN and no +inf (-inf is allowed)")
def c_lp_finite(raw: RawStream) -> tuple[str, str]:
    lp = _lp(raw)
    if lp is None:
        return skip("no 2-D log_probs")
    n_nan, n_pinf = int(np.isnan(lp).sum()), int(np.isposinf(lp).sum())
    if n_nan or n_pinf:
        return bad(f"{n_nan} NaN and {n_pinf} +inf values")
    return ok()


@check("NTS-NORM", "core", "MUST", "5.2.1", f"Each row of log_probs log-sum-exps to 0 (tolerance {NORM_TOL})")
def c_norm(raw: RawStream) -> tuple[str, str]:
    lp = _lp(raw)
    if lp is None:
        return skip("no 2-D log_probs")
    if lp.shape[0] == 0:
        return ok("no frames")
    if np.isnan(lp).any() or np.isposinf(lp).any():
        return skip("non-finite values (reported by NTS-LP-FINITE)")
    m = lp.max(axis=1, keepdims=True)
    m_safe = np.where(np.isfinite(m), m, 0.0)
    with np.errstate(divide="ignore"):
        lse = np.log(np.exp(lp - m_safe).sum(axis=1)) + m_safe[:, 0]
    badrows = np.where(~(np.abs(lse) <= NORM_TOL))[0]
    if badrows.size:
        t = int(badrows[0])
        return bad(f"{badrows.size} row(s) not normalised; frame {t} gives log-sum-exp {lse[t]:.4g}")
    return ok(f"max |log-sum-exp| = {float(np.max(np.abs(lse))):.2e}")


@check("NTS-FT-FINITE", "core", "MUST", "5.2.3", "frame_times are finite")
def c_ft_finite(raw: RawStream) -> tuple[str, str]:
    ft = raw.frame_times
    if ft is None:
        return skip("no frame_times")
    return ok() if np.all(np.isfinite(ft)) else bad("frame_times has non-finite values")


@check("NTS-FT-MONO", "core", "MUST", "5.2.3 / 6.2.4", "frame_times increase strictly")
def c_ft_mono(raw: RawStream) -> tuple[str, str]:
    ft = raw.frame_times
    if ft is None or ft.ndim != 1:
        return skip("no 1-D frame_times")
    if ft.size < 2:
        return ok("fewer than 2 frames")
    d = np.diff(ft)
    badi = np.where(~(d > 0))[0]
    if badi.size:
        i = int(badi[0])
        return bad(f"frame {i + 1} time {ft[i + 1]!r} is not greater than frame {i} time {ft[i]!r}")
    return ok()


@check("NTS-FRAME-PERIOD", "core", "MUST", "3.2 / 5.2.5", "frame_period, if present, is finite and > 0")
def c_frame_period(raw: RawStream) -> tuple[str, str]:
    if "frame_period" not in raw.header or raw.header["frame_period"] is None:
        return ok("absent")
    v = raw.header["frame_period"]
    return ok() if _is_num(v) and math.isfinite(v) and v > 0 else bad(f"frame_period {v!r} is not finite and > 0")


@check("NTS-LATENCY", "core", "MUST", "3.2 / 5.2.5", "latency, if present, is finite and >= 0")
def c_latency(raw: RawStream) -> tuple[str, str]:
    if "latency" not in raw.header or raw.header["latency"] is None:
        return ok("absent")
    v = raw.header["latency"]
    return ok() if _is_num(v) and math.isfinite(v) and v >= 0 else bad(f"latency {v!r} is not finite and >= 0")


# --- sparse frames (3.3) ---------------------------------------------------------------------


@check("NTS-SPARSE", "core", "MUST", "3.3", "Sparse frames: k values plus rest_log_prob are normalised", formats=("jsonl",))
def c_sparse(raw: RawStream) -> tuple[str, str]:
    if not raw.sparse_frames:
        return skip("no sparse frames")
    for f in raw.sparse_frames:
        if "_vals" not in f:
            continue  # malformed: reported by NTS-JSONL-FRAME
        vals = np.array(f["_vals"] + [f["_rest"]], dtype=np.float64)
        if np.isnan(vals).any() or np.isposinf(vals).any():
            return bad(f"line {f['_line']}: NaN or +inf in a sparse frame")
        m = vals.max()
        lse = math.log(np.exp(vals - m).sum()) + m if math.isfinite(m) else -math.inf
        if not abs(lse) <= NORM_TOL:
            return bad(f"line {f['_line']}: top-k plus rest log-sum-exp is {lse:.4g}")
    return ok(f"{len(raw.sparse_frames)} sparse frame(s)")


# --- semantic conventions (4.1, 4.2) ----------------------------------------------------------


@check("NTS-META-TYPES", "core", "MUST", "4.1 / 4.2", "Defined meta keys have the type and values of section 4.2")
def c_meta_types(raw: RawStream) -> tuple[str, str]:
    m = _meta(raw)
    if m is None:
        return skip("meta is not an object")
    errs = []
    for k, fn in DEFINED_KEYS.items():
        if k in m:
            want = fn(m[k])
            if want:
                errs.append(f"{k} = {m[k]!r} must be {want}")
    return bad("; ".join(errs)) if errs else ok(f"{sum(k in m for k in DEFINED_KEYS)} defined key(s) checked")


@check("NTS-META-LOOKAHEAD", "core", "MUST", "4.2", "decoder.lookahead_s equals latency when both are present")
def c_lookahead(raw: RawStream) -> tuple[str, str]:
    m = _meta(raw)
    lat = raw.header.get("latency")
    if m is None or "decoder.lookahead_s" not in m or lat is None:
        return skip("not both present")
    la = m["decoder.lookahead_s"]
    if not _is_num(la) or not _is_num(lat):
        return skip("not numeric (reported elsewhere)")
    return ok() if abs(float(la) - float(lat)) <= 1e-9 else bad(f"decoder.lookahead_s {la} != latency {lat}")


@check("NTS-NAMESPACE", ADVISORY, "SHOULD", "4.1", "meta keys are namespaced; custom keys avoid the defined namespaces")
def c_namespace(raw: RawStream) -> tuple[str, str]:
    m = _meta(raw)
    if m is None:
        return skip("meta is not an object")
    flat = [k for k in m if "." not in k and k not in DEFINED_KEYS]
    custom_in_defined = [k for k in m if "." in k and k not in DEFINED_KEYS and k.split(".")[0] in DEFINED_NAMESPACES]
    msgs = []
    if flat:
        msgs.append(f"not namespaced: {flat}")
    if custom_in_defined:
        msgs.append(f"custom keys inside a defined namespace: {custom_in_defined} (see ambiguity A2)")
    return bad("; ".join(msgs)) if msgs else ok()


@check("NTS-LEAK-KEYS", "core", "MUST", "5.3.1", "meta has no key that names ground truth or target labels", heuristic=True)
def c_leak_keys(raw: RawStream) -> tuple[str, str]:
    m = _meta(raw)
    if m is None:
        return skip("meta is not an object")
    hits = [p for p, _ in _walk(m) if re.split(r"[.\[]", p)[-1].lower() in LEAK_KEY_NAMES]
    return bad(f"keys that suggest ground truth: {hits}") if hits else ok()


@check("NTS-PRIVACY", "core", "MUST", "5.4.1 / 4.2", "meta has no personal identifiers (e-mail, name, birth date keys)", heuristic=True)
def c_privacy(raw: RawStream) -> tuple[str, str]:
    m = _meta(raw)
    if m is None:
        return skip("meta is not an object")
    hits = []
    for p, v in _walk(m):
        parts = [s.lower() for s in re.split(r"[.\[]", p)]
        last = parts[-1]
        if p not in DEFINED_KEYS and last in PII_KEY_NAMES:
            # "name" alone is common for models; flag it only under a person-like namespace.
            if last != "name" or any(s in _PERSON_NS for s in parts[:-1]) or len(parts) == 1:
                hits.append(f"key {p}")
        if isinstance(v, str) and _EMAIL_RE.search(v):
            hits.append(f"e-mail address in {p}")
    for k in ("stream.id", "consent.ref"):
        v = m.get(k)
        if isinstance(v, str) and (any(c.isspace() for c in v) and len(v.split()) > 3):
            hits.append(f"{k} looks like free text, not an opaque id")
    return bad("; ".join(sorted(set(hits)))) if hits else ok()


@check("NTS-FREE-TEXT", ADVISORY, "SHOULD NOT", "5.4.3", "meta has no free-text note fields", heuristic=True)
def c_free_text(raw: RawStream) -> tuple[str, str]:
    m = _meta(raw)
    if m is None:
        return skip("meta is not an object")
    hits = [p for p, _ in _walk(m) if re.split(r"[.\[]", p)[-1].lower() in FREE_TEXT_KEY_NAMES]
    return bad(f"free-text keys: {hits}") if hits else ok()


# --- vocabulary identity and kinds (3.1, 3.4) ----------------------------------------------------


@check("NTS-VOCAB-ID", "core", "MUST", "3.4", "If a header vocab_id names a known registry entry, vocab matches it")
def c_vocab_id(raw: RawStream) -> tuple[str, str]:
    vid = raw.header.get("vocab_id")
    if vid is None:
        return skip("no header vocab_id")
    if vid not in KNOWN_VOCAB_IDS:
        return skip(f"vocab_id {vid!r} is not in the suite's registry copy")
    return ok() if tuple(_vocab(raw) or ()) == KNOWN_VOCAB_IDS[vid] else bad(f"vocab does not match {vid}")


@check("NTS-VT-CHAR", "trust-ready", "PROFILE", "3.1", "char vocabulary: each non-blank token is one character")
def c_vt_char(raw: RawStream) -> tuple[str, str]:
    v = _vocab(raw)
    if raw.header.get("vocab_type") != "char" or v is None:
        return skip("not a char vocabulary")
    b = raw.header.get("blank_id")
    badt = [t for i, t in enumerate(v) if i != b and not (isinstance(t, str) and len(t) == 1)]
    return bad(f"tokens that are not one character: {badt[:6]}") if badt else ok()


@check("NTS-VT-KEY", ADVISORY, "SHOULD", "3.1 / 10.7", "key vocabulary: tokens are W3C KeyboardEvent.code names")
def c_vt_key(raw: RawStream) -> tuple[str, str]:
    v = _vocab(raw)
    if raw.header.get("vocab_type") != "key" or v is None:
        return skip("not a key vocabulary")
    b = raw.header.get("blank_id")
    badt = [t for i, t in enumerate(v) if i != b and not (isinstance(t, str) and _W3C_CODE_RE.match(t))]
    return bad(f"tokens that are not W3C code names: {badt[:6]}") if badt else ok()


@check("NTS-VT-PHONEME", ADVISORY, "SHOULD", "3.1 / 3.4", "phoneme vocabulary: tokens are ARPAbet (plus silence markers) or IPA")
def c_vt_phoneme(raw: RawStream) -> tuple[str, str]:
    v = _vocab(raw)
    if raw.header.get("vocab_type") != "phoneme" or v is None:
        return skip("not a phoneme vocabulary")
    b = raw.header.get("blank_id")
    toks = [t for i, t in enumerate(v) if i != b and isinstance(t, str)]
    arpa = all(t.upper().rstrip("012") in ARPABET or t in PHONEME_MARKERS for t in toks)
    ipa = all(any(ord(c) > 127 for c in t) or t.isalpha() and t.islower() and len(t) <= 3 or t in PHONEME_MARKERS
              for t in toks)
    if arpa:
        return ok("ARPAbet")
    if ipa and any(any(ord(c) > 127 for c in t) for t in toks):
        return ok("IPA")
    return bad("tokens are neither ARPAbet nor IPA (an encoded phoneme set? see ambiguity A3)")


@check("NTS-VT-OTHER", ADVISORY, "SHOULD", "3.1", "vocab_type other: meta describes the tokens")
def c_vt_other(raw: RawStream) -> tuple[str, str]:
    if raw.header.get("vocab_type") != "other":
        return skip("not vocab_type other")
    m = _meta(raw) or {}
    return ok() if any("vocab" in k for k in m) or raw.header.get("vocab_id") else bad("no meta key describes the vocabulary")


@check("NTS-BLANK-TOKEN", ADVISORY, "SHOULD", "3.1", "The blank token is not a whitespace or empty string")
def c_blank_token(raw: RawStream) -> tuple[str, str]:
    v, b = _vocab(raw), raw.header.get("blank_id")
    if v is None or not _is_int(b) or not 0 <= b < len(v):
        return skip("no valid blank")
    t = v[b]
    return bad(f"blank token {t!r} can be confused with text") if isinstance(t, str) and not t.strip() else ok()


# --- honest probabilities (2.4) -------------------------------------------------------------


@check("NTS-SHARPENED", ADVISORY, "MUST NOT", "2.4.4", "Rows are not all one-hot (a sign of sharpened output)", heuristic=True)
def c_sharpened(raw: RawStream) -> tuple[str, str]:
    lp = _lp(raw)
    if lp is None or lp.shape[0] < 10 or np.isnan(lp).any():
        return skip("fewer than 10 frames")
    frac = float(np.mean(lp.max(axis=1) >= -1e-6))
    return bad(f"{frac:.0%} of rows are one-hot") if frac > 0.9 else ok(f"{frac:.0%} one-hot rows")


@check("NTS-FP-CONSIST", ADVISORY, "SHOULD", "3.2", "frame_period agrees with the median frame step (within 25 %)")
def c_fp_consist(raw: RawStream) -> tuple[str, str]:
    fp, ft = raw.header.get("frame_period"), raw.frame_times
    if not _is_num(fp) or ft is None or ft.ndim != 1 or ft.size < 3 or not fp > 0:
        return skip("no frame_period or fewer than 3 frames")
    med = float(np.median(np.diff(ft)))
    return ok(f"median step {med:.4g} s") if abs(med - fp) <= 0.25 * fp else bad(f"median step {med:.4g} s vs frame_period {fp}")


# --- events (3.5-3.9, Development) ------------------------------------------------------------


def _events(raw: RawStream, typ: str) -> list[dict]:
    return [e for e in raw.events if e.get("type") == typ]


def _score_errors(e: dict, need_semantics: bool) -> list[str]:
    errs = []
    sem = e.get("score_semantics")
    if sem is None:
        if need_semantics:
            errs.append("no score_semantics")
        return errs
    if sem not in SCORE_SEMANTICS:
        return [f"score_semantics {sem!r} is not one of {list(SCORE_SEMANTICS)}"]
    sc = e.get("score")
    if sem in ("calibrated_prob", "uncalibrated_prob") and sc is not None and not (_is_num(sc) and 0 <= sc <= 1):
        errs.append(f"score {sc!r} is not in [0, 1] for {sem} (3.5 rule 2)")
    if sem in ("power", "strength"):
        rng = e.get("score_range")
        if not (isinstance(rng, list) and len(rng) == 2 and all(_is_num(x) for x in rng)):
            errs.append(f"score_semantics {sem} needs score_range [min, max] (3.5 table)")
    if sem == "none" and sc is not None:
        errs.append("score_semantics none needs a null or absent score")
    return errs


@check("NTS-EVT-DECISION", "core", "MUST", "3.5", "decision events: label, t, score_semantics and score rules", formats=("jsonl",))
def c_evt_decision(raw: RawStream) -> tuple[str, str]:
    evs = _events(raw, "decision")
    if not evs:
        return skip("no decision events")
    errs = []
    for e in evs:
        n = e["_line"]
        if not isinstance(e.get("label"), str):
            errs.append(f"line {n}: no string label")
        if not _is_num(e.get("t")):
            errs.append(f"line {n}: no numeric t")
        errs += [f"line {n}: {x}" for x in _score_errors(e, need_semantics=True)]
    return bad("; ".join(errs)) if errs else ok(f"{len(evs)} decision event(s)")


@check("NTS-EVT-LABEL", ADVISORY, "SHOULD", "3.5", "decision labels are tokens in vocab", formats=("jsonl",))
def c_evt_label(raw: RawStream) -> tuple[str, str]:
    evs, v = _events(raw, "decision"), _vocab(raw)
    if not evs or v is None:
        return skip("no decision events")
    out = sorted({e.get("label") for e in evs if e.get("label") not in v}, key=str)
    return bad(f"labels not in vocab: {out[:5]}") if out else ok()


@check("NTS-EVT-HYPOTHESIS", "core", "MUST", "3.6", "hypothesis events: id, nbest, score_semantics, is_final", formats=("jsonl",))
def c_evt_hyp(raw: RawStream) -> tuple[str, str]:
    evs = _events(raw, "hypothesis")
    if not evs:
        return skip("no hypothesis events")
    errs, ids = [], set()
    for e in evs:
        n = e["_line"]
        if not isinstance(e.get("id"), str):
            errs.append(f"line {n}: no string id")
        elif e["id"] in ids:
            errs.append(f"line {n}: id {e['id']!r} is not unique")
        else:
            ids.add(e["id"])
        nb = e.get("nbest")
        if not isinstance(nb, list) or not all(isinstance(x, dict) and isinstance(x.get("text"), str) and _is_num(x.get("score"))
                                               for x in nb):
            errs.append(f"line {n}: nbest must be a list of {{text, score}}")
        if not isinstance(e.get("is_final"), bool):
            errs.append(f"line {n}: is_final must be a boolean")
        errs += [f"line {n}: {x}" for x in _score_errors({**e, "score": None}, need_semantics=True)]
    return bad("; ".join(errs)) if errs else ok(f"{len(evs)} hypothesis event(s)")


@check("NTS-EVT-POINTER", "core", "MUST", "3.7", "pointer events: t, dims 1-3, mode, values", formats=("jsonl",))
def c_evt_pointer(raw: RawStream) -> tuple[str, str]:
    evs = _events(raw, "pointer")
    if not evs:
        return skip("no pointer events")
    errs = []
    for e in evs:
        n, d = e["_line"], e.get("dims")
        if not _is_num(e.get("t")):
            errs.append(f"line {n}: no numeric t")
        if not (_is_int(d) and 1 <= d <= 3):
            errs.append(f"line {n}: dims must be 1-3")
            continue
        if e.get("mode") not in ("relative", "absolute"):
            errs.append(f"line {n}: mode must be relative or absolute")
        vals = e.get("values")
        if not (isinstance(vals, list) and len(vals) == d and all(_is_num(x) for x in vals)):
            errs.append(f"line {n}: values must be {d} numbers")
        elif e.get("mode") == "absolute":
            absent = e.get("absent") or [False] * d
            if any(not a and not 0 <= x <= 1 for x, a in zip(vals, absent)):
                errs.append(f"line {n}: absolute values must be in [0, 1]")
    return bad("; ".join(errs)) if errs else ok(f"{len(evs)} pointer event(s)")


@check("NTS-EVT-SIGNAL-QUALITY", "core", "MUST", "3.9", "signal_quality events: t, value, unit; index in [0, 1]", formats=("jsonl",))
def c_evt_sq(raw: RawStream) -> tuple[str, str]:
    evs = _events(raw, "signal_quality")
    if not evs:
        return skip("no signal_quality events")
    errs = []
    for e in evs:
        n = e["_line"]
        if not _is_num(e.get("t")) or not _is_num(e.get("value")):
            errs.append(f"line {n}: needs numeric t and value")
        if e.get("unit") not in SQ_UNITS:
            errs.append(f"line {n}: unit must be one of {list(SQ_UNITS)}")
        elif e["unit"] == "index" and _is_num(e.get("value")) and not 0 <= e["value"] <= 1:
            errs.append(f"line {n}: index value must be in [0, 1]")
    return bad("; ".join(errs)) if errs else ok(f"{len(evs)} signal_quality event(s)")


@check("NTS-EVT-TIMING", "core", "MUST", "3.8", "t_signal_start <= t_signal_end <= t_decoded <= t_emitted when present",
       formats=("jsonl",))
def c_evt_timing(raw: RawStream) -> tuple[str, str]:
    keys = ("t_signal_start", "t_signal_end", "t_decoded", "t_emitted")
    evs = [e for e in raw.events if any(k in e for k in keys)]
    if not evs:
        return skip("no extended timing")
    errs = []
    for e in evs:
        vals = [(k, e[k]) for k in keys if k in e]
        if not all(_is_num(v) for _, v in vals):
            errs.append(f"line {e['_line']}: timing values must be numbers")
            continue
        for (k1, v1), (k2, v2) in zip(vals, vals[1:]):
            if v1 > v2:
                errs.append(f"line {e['_line']}: {k1} {v1} > {k2} {v2}")
    return bad("; ".join(errs)) if errs else ok()


@check("NTS-CLOCK", "core", "MUST", "3.8", "clock_domain, if present, is lsl, unix, monotonic, trial or other")
def c_clock(raw: RawStream) -> tuple[str, str]:
    if "clock_domain" not in raw.header:
        return ok("absent (default trial)")
    cd = raw.header["clock_domain"]
    return ok() if cd in CLOCK_DOMAINS else bad(f"clock_domain {cd!r} is not one of {list(CLOCK_DOMAINS)}")


# --- trust-ready profile -------------------------------------------------------------------


@check("TR-SOURCE", "trust-ready", "PROFILE", "3.2", 'source names the producer (present and not "unknown")')
def c_tr_source(raw: RawStream) -> tuple[str, str]:
    s = raw.header.get("source")
    return ok() if isinstance(s, str) and s and s != "unknown" else bad("source is absent or \"unknown\"")


@check("TR-MODALITY", "trust-ready", "PROFILE", "4.2", "meta has device.modality")
def c_tr_modality(raw: RawStream) -> tuple[str, str]:
    m = _meta(raw) or {}
    return ok(str(m["device.modality"])) if "device.modality" in m else bad("no device.modality")


@check("TR-CAUSAL", "trust-ready", "SHOULD", "3.2 / 4.2", "meta has decoder.causal")
def c_tr_causal(raw: RawStream) -> tuple[str, str]:
    m = _meta(raw) or {}
    return ok() if "decoder.causal" in m else bad("no decoder.causal (a consumer cannot tell online from offline output)")


@check("TR-OFFLINE-LATENCY", "trust-ready", "SHOULD", "3.2", "A non-causal (offline) decoder omits latency")
def c_tr_offline(raw: RawStream) -> tuple[str, str]:
    m = _meta(raw) or {}
    if m.get("decoder.causal") is not False:
        return skip("decoder.causal is not false")
    if raw.header.get("latency") is not None:
        return bad("decoder.causal is false but latency is set (see ambiguity A1)")
    return ok()


@check("TR-DERIVED", "trust-ready", "SHOULD", "4.2 / 5.4.4", "meta has data.derived = true")
def c_tr_derived(raw: RawStream) -> tuple[str, str]:
    m = _meta(raw) or {}
    if "data.derived" not in m:
        return bad("no data.derived")
    return ok() if m["data.derived"] is True else bad(f"data.derived is {m['data.derived']!r}")


_CALIB_HINT = re.compile(r"calibrat|temperature", re.I)


@check("TR-CALIB", "trust-ready", "MUST", "4.1 / 4.2 / 3.5.3", "calibration.applied is consistent with the calibration keys")
def c_tr_calib(raw: RawStream) -> tuple[str, str]:
    m = _meta(raw) or {}
    applied = m.get("calibration.applied", False)
    if applied is True:
        meth = m.get("decoder.calibration_method")
        if not isinstance(meth, str) or meth in ("", "none"):
            return bad("calibration.applied is true but decoder.calibration_method is absent or \"none\"")
        return ok()
    hints = [k for k in m if _CALIB_HINT.search(k) and k not in DEFINED_KEYS and m[k] not in (None, False, 1, 1.0)]
    if hints:
        return bad(f"keys {hints} suggest a calibration step, but calibration.applied is not true (default false)")
    return ok()


@check("TR-LANGUAGE", "trust-ready", "PROFILE", "4.2", "Text vocabularies (char, word, phoneme) state the language")
def c_tr_language(raw: RawStream) -> tuple[str, str]:
    if raw.header.get("vocab_type") not in ("char", "word", "phoneme"):
        return skip("not a text vocabulary")
    m = _meta(raw) or {}
    return ok(str(m["language"])) if "language" in m else bad("no language")


# --- provenance profile (4.3) -----------------------------------------------------------------


@check("PV-STREAM-ID", "provenance", "PROFILE", "4.3.1", "meta has an opaque stream.id")
def c_pv_stream_id(raw: RawStream) -> tuple[str, str]:
    m = _meta(raw) or {}
    return ok() if isinstance(m.get("stream.id"), str) and m["stream.id"] else bad("no stream.id (a consumer must hash the content)")


@check("PV-DECODER", "provenance", "SHOULD", "4.3.2", "meta has decoder.name and decoder.version")
def c_pv_decoder(raw: RawStream) -> tuple[str, str]:
    m = _meta(raw) or {}
    miss = [k for k in ("decoder.name", "decoder.version") if k not in m]
    return bad(f"missing {miss}") if miss else ok()


@check("PV-WEIGHTS", "provenance", "SHOULD", "4.2 / 4.3.2", "meta has decoder.weights_sha256")
def c_pv_weights(raw: RawStream) -> tuple[str, str]:
    m = _meta(raw) or {}
    return ok() if "decoder.weights_sha256" in m else bad("no decoder.weights_sha256")


@check("PV-ADAPTER", "provenance", "SHOULD", "4.2 / 4.3.2", "adapter.name and adapter.version are both present or both absent")
def c_pv_adapter(raw: RawStream) -> tuple[str, str]:
    m = _meta(raw) or {}
    a, b = "adapter.name" in m, "adapter.version" in m
    if a != b:
        return bad("only one of adapter.name / adapter.version")
    return ok("adapter keys present" if a else "no adapter keys")


@check("PV-CALIB-ID", "provenance", "SHOULD", "3.5.3 / 4.3.2", "A calibrated stream has decoder.calibration_id")
def c_pv_calib_id(raw: RawStream) -> tuple[str, str]:
    m = _meta(raw) or {}
    if m.get("calibration.applied") is not True:
        return skip("calibration.applied is not true")
    return ok() if "decoder.calibration_id" in m else bad("no decoder.calibration_id")


@check("PV-PSEUDONYM", "provenance", "MUST", "5.4.2 / 4.3.4", "subject.id and session.id look like pseudonymous codes", heuristic=True)
def c_pv_pseudo(raw: RawStream) -> tuple[str, str]:
    m = _meta(raw) or {}
    errs = [f"{k} = {m[k]!r}" for k in ("subject.id", "session.id")
            if isinstance(m.get(k), str) and not _PSEUDO_ID_RE.match(m[k])]
    return bad(f"ids that do not look like codes: {errs}") if errs else ok()


# --- runner -------------------------------------------------------------------------------


def run_checks(raw: RawStream, truth: Iterable[str] | None = None) -> list[CheckResult]:
    """Run every check that applies to the format of ``raw``.

    If ``truth`` (ground-truth texts) is given, the extra check
    ``NTS-LEAK-TRUTH`` (5.3.1) fails when a truth text appears in a
    header string of the stream.
    """
    out: list[CheckResult] = []
    parse_failed = not raw.parsed
    for c in REGISTRY:
        if raw.format not in c.formats:
            continue
        if parse_failed and c.check_id not in ("NTS-PARSE", "NTS-JSONL-HEADER"):
            status, msg = SKIP, "the file did not parse"
        else:
            try:
                status, msg = c.fn(raw)
            except Exception as e:  # a check must never crash the suite
                status, msg = FAIL, f"check raised {type(e).__name__}: {e}"
        out.append(CheckResult(c.check_id, c.level, c.keyword, c.clause, c.title, status, msg, c.heuristic))
    if truth is not None:
        out.append(_leak_truth(raw, list(truth)))
    return out


def _leak_truth(raw: RawStream, truth: list[str]) -> CheckResult:
    texts = [t for t in truth if isinstance(t, str) and len(t.strip()) >= 4]
    hay = json.dumps({k: v for k, v in raw.header.items() if not k.startswith("_")}, ensure_ascii=False, default=str).lower()
    hits = [t for t in texts if t.lower() in hay]
    status = FAIL if hits else (PASS if texts else SKIP)
    msg = f"truth text found in the header/meta: {hits[:3]}" if hits else f"{len(texts)} truth text(s) not found"
    return CheckResult("NTS-LEAK-TRUTH", "core", "MUST", "5.3.1", "No ground-truth text appears in the header or meta",
                       status, msg, False)


def check_table() -> list[dict[str, Any]]:
    """The list of all checks (for docs and ``--list``)."""
    rows = [{"id": c.check_id, "level": c.level, "keyword": c.keyword, "clause": c.clause, "title": c.title,
             "heuristic": c.heuristic, "formats": list(c.formats)} for c in REGISTRY]
    rows.append({"id": "NTS-LEAK-TRUTH", "level": "core", "keyword": "MUST", "clause": "5.3.1",
                 "title": "No ground-truth text appears in the header or meta (only with --truth)", "heuristic": False,
                 "formats": ["npz", "jsonl", "object"]})
    return rows
