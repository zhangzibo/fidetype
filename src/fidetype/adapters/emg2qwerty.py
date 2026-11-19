"""emg2qwerty adapter: wrist sEMG during touch typing -> NeuralTextStream.

Source: Sivakumar et al., "emg2qwerty: A large dataset with baselines for
touch typing using surface electromyography", NeurIPS 2024 Datasets and
Benchmarks (arXiv:2410.20081), Meta. Data:
``emg2qwerty-data-2021-08.tar.gz`` (:data:`ARCHIVE_URL`). Licence: the
repository ``LICENSE`` file is **CC BY-NC-SA 4.0** (the README says
CC BY-NC 4.0; we follow the stricter one). **Research use only.** Streams,
weights and results derived from this data are non-commercial and keep
the share-alike terms.

This is our own code (Apache-2.0). We read only the HDF5 files and
``metadata.csv``. Nothing is copied from Meta's code.

Safe loading
------------
The files are untrusted downloads. This module opens them with
:mod:`h5py` (optional extra ``[emg2qwerty]``) in read-only mode and reads
only plain numeric datasets and string attributes. The keystroke and
prompt logs are JSON strings; they are parsed with :func:`json.loads`
and checked field by field. Nothing is unpickled and no code from the
archive runs. Attribute sizes are limited (:data:`MAX_ATTR_BYTES`).

File layout (checked on all 1,135 files, 2026-11-15)
----------------------------------------------------
- One group ``emg2qwerty``. Attributes (all strings unless noted):
  ``session_name``, ``user`` (an 8-digit pseudonym), ``condition``
  (always ``on_keyboard``), ``daq_sample_rate`` (``"2000.0"``),
  ``daq_channels`` (``"16"``), ``schedule``, ``duration_mins`` (float),
  ``quality_check_tags`` (array), ``keystrokes`` (JSON list) and
  ``prompts`` (JSON list).
- One dataset ``emg2qwerty/timeseries``: a 1-D compound array, one row
  per sample, fields ``emg_right`` (16 x float32), ``time`` (float64,
  unix seconds) and ``emg_left`` (16 x float32). Contiguous, not
  compressed. Up to 5,701,122 rows (about 775 MB) per file.
- ``keystrokes``: ``{"ascii", "key", "start", "end"}`` per key press.
  ``key`` is the character (``"a"``, ``"."``) or a ``Key.<name>`` string
  (``Key.space``, ``Key.backspace``, ``Key.enter``, ...). ``start`` is
  the key-down time and ``end`` the key-up time, unix seconds, on the
  same clock as ``time``. The list is sorted by ``start``.
- ``prompts``: ``{"name", "start", "end", "payload", "payload_type"}``.
  ``name == "text_prompt"`` items have ``payload = {"prompt_num",
  "text"}``; the text ends with ``U+23CE`` (the Enter key the typist
  presses to finish the prompt). Text prompts do not overlap.

Our checks: the sample times step 0.45-0.55 ms (2 kHz); 5,258,056 key
presses in the files (``metadata.csv`` says 5,262,671); 2,975 (0.057 %)
fall outside their recording; 99.3-100 % of the key presses of a session
fall inside a text prompt.

Streams
-------
The dataset has no decoder output. A replay stream comes from a decoder
that classifies one EMG window per key press (oracle key timing from the
keylogger, as in the KT-sEMG and Toronto sEMG adapters).
:func:`prompt_stream` makes one stream per text prompt and one frame per
key press inside the prompt. The frame time is seconds from the first
EMG sample of the session. Vocabulary: the 32 W3C ``KeyboardEvent.code``
classes of :data:`fidetype.adapters.kt_semg.KEY_VOCAB` (the same
``fidetype.vocab_id``), ``vocab_type="key"``, ``blank_id=None``. Key
presses outside the vocabulary (arrows, digits, modifiers; < 0.2 %)
still get a frame.

The reference decoder is :class:`fidetype.adapters.kt_semg.LdaKeyDecoder`
(shrinkage LDA on log-RMS window features, numpy only). The
``baseline`` command fits it per session and replays the held-out half.
It is a baseline for replay tests, not a result.

No user id, session name, date or text goes into ``meta``. A session is
named by its ordinal in the run; ``stream.id`` is a truncated SHA-256 of
the dataset slug, the session name and the prompt index.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from dataclasses import dataclass
from os import PathLike
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from fidetype import __version__ as _FIDETYPE_VERSION
from fidetype.adapters import kt_semg as _kt
from fidetype.streams.spec import NeuralTextStream

# --- dataset constants ----------------------------------------------------------

ARXIV_ID = "2410.20081"
REPO_URL = "https://github.com/facebookresearch/emg2qwerty"
ARCHIVE_URL = "https://fb-ctrl-oss.s3.amazonaws.com/emg2qwerty/emg2qwerty-data-2021-08.tar.gz"
ARCHIVE_SIZE = 308_382_645_571
#: Our own SHA-256 of the archive (2026-11-15). Meta publishes no checksum.
ARCHIVE_SHA256 = "7b2d827d0068b838e0a15ffe9d5ddddbdc315f55ba1b667636c84e6b510d7581"
LICENCE = "CC-BY-NC-SA-4.0"
ATTRIBUTION = "emg2qwerty dataset, Sivakumar et al. 2024 (Meta), CC BY-NC-SA 4.0, research use only"
DATASET_SLUG = "emg2qwerty"
ADAPTER_NAME = "fidetype.adapters.emg2qwerty"

GROUP = "emg2qwerty"
TIMESERIES = "timeseries"
SAMPLE_RATE_HZ = 2000.0
CHANNELS_PER_BAND = 16
N_CHANNELS = 2 * CHANNELS_PER_BAND
#: Channel order of the arrays this module returns: left band, then right band.
BAND_FIELDS = ("emg_left", "emg_right")
#: Upper limit for one JSON attribute (untrusted input). The largest real one is a few MB.
MAX_ATTR_BYTES = 64_000_000
PROMPT_END_MARK = "⏎"

# --- vocabulary -------------------------------------------------------------------

KEY_VOCAB = _kt.KEY_VOCAB
KEY_VOCAB_ID = _kt.KEY_VOCAB_ID
_CODE_INDEX = {c: i for i, c in enumerate(KEY_VOCAB)}

#: ``Key.<name>`` strings of the keylogger -> W3C ``KeyboardEvent.code``.
_NAMED_KEYS: dict[str, str] = {
    "Key.space": "Space", "Key.backspace": "Backspace", "Key.enter": "Enter", "Key.tab": "Tab",
    "Key.left": "ArrowLeft", "Key.right": "ArrowRight", "Key.up": "ArrowUp", "Key.down": "ArrowDown",
    "Key.shift": "ShiftLeft", "Key.shift_r": "ShiftRight", "Key.caps_lock": "CapsLock",
    "Key.ctrl": "ControlLeft", "Key.ctrl_l": "ControlLeft", "Key.ctrl_r": "ControlRight",
    "Key.alt": "AltLeft", "Key.alt_l": "AltLeft", "Key.alt_gr": "AltRight",
    "Key.cmd": "MetaLeft", "Key.cmd_r": "MetaRight", "Key.esc": "Escape", "Key.delete": "Delete",
    "Key.home": "Home", "Key.page_down": "PageDown",
}
_CHAR_TYPED = {"Key.space": " ", "Key.backspace": "\x08", "Key.enter": "\r", "Key.tab": "\t"}


def key_code(key: str) -> str | None:
    """W3C ``KeyboardEvent.code`` of a logged ``key`` string, or None if unknown."""
    if key in _NAMED_KEYS:
        return _NAMED_KEYS[key]
    return _kt.key_code(key) if len(key) == 1 else None


def key_class(key: str) -> int | None:
    """Index of a logged ``key`` string in :data:`KEY_VOCAB`, or None (not a class)."""
    code = key_code(key)
    return _CODE_INDEX.get(code) if code is not None else None


def typed_char(key: str) -> str:
    """The character a key press types (``\\x08`` = Backspace, ``\\r`` = Enter); ``""`` for other named keys."""
    if len(key) == 1:
        return key
    return _CHAR_TYPED.get(key, "")


# --- parsed records -------------------------------------------------------------------


@dataclass(frozen=True)
class Keystroke:
    """One key press of the keylogger. ``key`` is ground truth: it never goes into a stream."""

    start: float  # key-down, unix seconds
    end: float  # key-up, unix seconds
    key: str

    @property
    def code(self) -> str | None:
        return key_code(self.key)


@dataclass(frozen=True)
class Prompt:
    """One text prompt. ``text`` is ground truth (the end mark removed): it never goes into a stream."""

    index: int  # position among the text prompts of the session
    prompt_num: int | None
    start: float
    end: float
    text: str


def _finite(x: Any, what: str) -> float:
    if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x):
        raise ValueError(f"{what} is not a finite number")
    return float(x)


def _no_constant(c: str) -> Any:
    raise ValueError(f"JSON constant {c} not allowed")


def _json_list(raw: Any, what: str) -> list[Any]:
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    if not isinstance(raw, str):
        raise ValueError(f"{what} is not a JSON string")
    if len(raw) > MAX_ATTR_BYTES:
        raise ValueError(f"{what} is too large ({len(raw)} characters)")
    val = json.loads(raw, parse_constant=_no_constant)
    if not isinstance(val, list):
        raise ValueError(f"{what} is not a JSON list")
    return val


def parse_keystrokes(raw: str | bytes) -> list[Keystroke]:
    """Parse the ``keystrokes`` attribute. Raises ``ValueError`` on a bad item."""
    out = []
    for i, d in enumerate(_json_list(raw, "keystrokes")):
        if not isinstance(d, dict) or not isinstance(d.get("key"), str) or len(d["key"]) > 64:
            raise ValueError(f"keystroke {i} has no valid 'key'")
        s, e = _finite(d.get("start"), f"keystroke {i} start"), _finite(d.get("end"), f"keystroke {i} end")
        out.append(Keystroke(s, e, d["key"]))
    out.sort(key=lambda k: k.start)
    return out


def parse_prompts(raw: str | bytes) -> list[Prompt]:
    """The text prompts of the ``prompts`` attribute, in time order. Other prompt kinds are skipped."""
    out = []
    for i, d in enumerate(_json_list(raw, "prompts")):
        if not isinstance(d, dict):
            raise ValueError(f"prompt {i} is not an object")
        if d.get("name") != "text_prompt":
            continue
        pl = d.get("payload")
        if not isinstance(pl, dict) or not isinstance(pl.get("text"), str):
            raise ValueError(f"text prompt {i} has no payload text")
        num = pl.get("prompt_num")
        num = int(num) if isinstance(num, int) and not isinstance(num, bool) else None
        s, e = _finite(d.get("start"), f"prompt {i} start"), _finite(d.get("end"), f"prompt {i} end")
        if e < s:
            raise ValueError(f"prompt {i} ends before it starts")
        out.append((s, e, num, pl["text"].replace(PROMPT_END_MARK, "")))
    out.sort(key=lambda x: x[0])
    return [Prompt(j, num, s, e, txt) for j, (s, e, num, txt) in enumerate(out)]


def _attr_str(attrs: Any, name: str) -> str:
    v = attrs.get(name)
    if isinstance(v, bytes):
        v = v.decode("utf-8")
    if not isinstance(v, str):
        raise ValueError(f"attribute {name!r} missing or not a string")
    return v


# --- session files ------------------------------------------------------------------------


class Session:
    """One emg2qwerty HDF5 session, opened read-only.

    Use as a context manager (or call :meth:`close`). The EMG is read on
    demand in row ranges; only the sample times are kept in memory
    (8 bytes per sample). ``user`` and ``name`` are dataset pseudonyms:
    they never go into a stream.
    """

    def __init__(self, path: str | PathLike[str]):
        import h5py  # optional dependency ([emg2qwerty] extra)

        p = Path(path)
        if p.suffix.lower() not in (".hdf5", ".h5"):
            raise ValueError(f"not an HDF5 file: {p.name}")
        self.path = p
        self._f = h5py.File(p, "r")
        try:
            g = self._f.get(GROUP)
            if not isinstance(g, h5py.Group):
                raise ValueError(f"no group {GROUP!r}")
            ds = g.get(TIMESERIES)
            if not isinstance(ds, h5py.Dataset) or ds.ndim != 1 or ds.dtype.names is None:
                raise ValueError(f"no 1-D compound dataset {GROUP}/{TIMESERIES}")
            names = set(ds.dtype.names)
            for f in (*BAND_FIELDS, "time"):
                if f not in names:
                    raise ValueError(f"field {f!r} missing")
            for f in BAND_FIELDS:
                sub = ds.dtype.fields[f][0]
                if sub.shape != (CHANNELS_PER_BAND,) or sub.base.kind != "f":
                    raise ValueError(f"field {f!r} is not {CHANNELS_PER_BAND} floats")
            if ds.dtype.fields["time"][0].kind != "f":
                raise ValueError("field 'time' is not a float")
            rate = float(_attr_str(g.attrs, "daq_sample_rate"))
            if rate != SAMPLE_RATE_HZ:
                raise ValueError(f"sample rate {rate} Hz, expected {SAMPLE_RATE_HZ}")
            self.name = _attr_str(g.attrs, "session_name")
            self.user = _attr_str(g.attrs, "user")
            self.condition = _attr_str(g.attrs, "condition")
            self.keystrokes = parse_keystrokes(_attr_str(g.attrs, "keystrokes"))
            self.prompts = parse_prompts(_attr_str(g.attrs, "prompts"))
            self._ds = ds
            self._times: np.ndarray | None = None
        except Exception:
            self._f.close()
            raise

    def __enter__(self) -> "Session":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def close(self) -> None:
        self._f.close()

    @property
    def n_samples(self) -> int:
        return int(self._ds.shape[0])

    @property
    def times(self) -> np.ndarray:
        """Unix time of every sample (float64), read once."""
        if self._times is None:
            t = np.asarray(self._ds.fields("time")[:], dtype=np.float64)
            if t.size and (not np.all(np.isfinite(t)) or np.any(np.diff(t) <= 0)):
                raise ValueError("sample times are not finite and strictly increasing")
            self._times = t
        return self._times

    @property
    def t0(self) -> float:
        return float(self.times[0]) if self.n_samples else 0.0

    @property
    def duration_s(self) -> float:
        return float(self.times[-1] - self.times[0]) if self.n_samples else 0.0

    def read_emg(self, lo: int, hi: int) -> np.ndarray:
        """Rows ``[lo, hi)`` as a ``(n, 32)`` float32 array: left band channels 0-15, right band 16-31."""
        lo, hi = max(int(lo), 0), min(int(hi), self.n_samples)
        if hi <= lo:
            return np.zeros((0, N_CHANNELS), np.float32)
        left = np.asarray(self._ds.fields(BAND_FIELDS[0])[lo:hi], dtype=np.float32)
        right = np.asarray(self._ds.fields(BAND_FIELDS[1])[lo:hi], dtype=np.float32)
        return np.concatenate([left, right], axis=1)

    def sample_index(self, unix_times: Sequence[float]) -> np.ndarray:
        """Index of the nearest sample for each unix time (clipped to the recording)."""
        t = self.times
        u = np.asarray(unix_times, dtype=np.float64)
        i = np.clip(np.searchsorted(t, u), 1, max(len(t) - 1, 1))
        left_closer = (u - t[i - 1]) <= (t[i] - u)
        return np.clip(np.where(left_closer, i - 1, i), 0, max(len(t) - 1, 0)).astype(np.int64)


def list_sessions(root: str | PathLike[str]) -> list[Path]:
    """All ``*.hdf5`` session files directly under ``root``, sorted by name."""
    return sorted(Path(root).glob("*.hdf5"))


@dataclass(frozen=True)
class MetadataRow:
    user: str
    session: str
    duration_mins: float
    num_keystrokes: int
    num_prompts: int
    quality_check_tags: str


def read_metadata(path: str | PathLike[str], max_bytes: int = 10_000_000) -> list[MetadataRow]:
    """Read ``metadata.csv`` (header + one row per session)."""
    p = Path(path)
    if p.stat().st_size > max_bytes:
        raise ValueError(f"metadata file too large ({p.stat().st_size} bytes)")
    out = []
    with open(p, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            out.append(MetadataRow(r["user"], r["session"], float(r["duration_mins"]), int(r["num_keystrokes"]),
                                   int(r["num_prompts"]), r.get("quality_check_tags", "")))
    return out


def metadata_summary(rows: Sequence[MetadataRow]) -> dict[str, Any]:
    """Aggregate counts only (no per-user numbers)."""
    users = {r.user for r in rows}
    per_user = np.bincount(np.unique([r.user for r in rows], return_inverse=True)[1]) if rows else np.zeros(0)
    return {
        "sessions": len(rows),
        "users": len(users),
        "hours": round(sum(r.duration_mins for r in rows) / 60.0, 1),
        "keystrokes": int(sum(r.num_keystrokes for r in rows)),
        "prompts": int(sum(r.num_prompts for r in rows)),
        "sessions_with_quality_tags": int(sum(1 for r in rows if r.quality_check_tags.strip() not in ("", "[]"))),
        "sessions_per_user_min_median_max": [int(per_user.min()), float(np.median(per_user)), int(per_user.max())]
        if len(per_user) else [],
    }


def select_subset(rows: Sequence[MetadataRow], n_users: int, sessions_per_user: int) -> list[list[str]]:
    """The documented baseline subset: session names grouped by user.

    Users sorted by id; the first ``n_users`` that have at least
    ``sessions_per_user`` sessions; for each, the first sessions in name
    order (names start with the date).
    """
    by_user: dict[str, list[str]] = {}
    for r in rows:
        by_user.setdefault(r.user, []).append(r.session)
    out = []
    for u in sorted(by_user):
        s = sorted(by_user[u])
        if len(s) >= sessions_per_user:
            out.append(s[:sessions_per_user])
        if len(out) == n_users:
            break
    return out


# --- key events -------------------------------------------------------------------------


@dataclass(frozen=True)
class KeyEvent:
    """A key press inside the recording. ``t``: seconds from the first EMG sample; ``sample``: its row."""

    t: float
    sample: int
    key: str


def key_events(sess: Session, keystrokes: Sequence[Keystroke] | None = None, margin_s: float = 0.0) -> list[KeyEvent]:
    """Key presses with ``margin_s <= t <= duration - margin_s``, strictly increasing in time.

    Two presses with the same key-down time keep only the first.
    """
    ks = sess.keystrokes if keystrokes is None else keystrokes
    if not ks or sess.n_samples == 0:
        return []
    t0, dur = sess.t0, sess.duration_s
    rel = np.array([k.start for k in ks]) - t0
    keep = (rel >= margin_s) & (rel <= dur - margin_s)
    idx = sess.sample_index(np.array([k.start for k in ks])[keep]) if keep.any() else np.zeros(0, np.int64)
    out: list[KeyEvent] = []
    for k, r, i in zip((k for k, m in zip(ks, keep) if m), rel[keep], idx):
        if out and r <= out[-1].t:
            continue
        out.append(KeyEvent(float(r), int(i), k.key))
    return out


def prompt_events(sess: Session, prompt: Prompt, events: Sequence[KeyEvent] | None = None) -> list[KeyEvent]:
    """The key events whose key-down time falls inside ``[prompt.start, prompt.end]``."""
    ev = key_events(sess) if events is None else events
    a, b = prompt.start - sess.t0, prompt.end - sess.t0
    return [e for e in ev if a <= e.t <= b]


def typed_text(events: Sequence[KeyEvent]) -> str:
    """The keystroke sequence as text (Backspace = ``\\x08``, Enter = ``\\r``). Ground truth only."""
    return "".join(typed_char(e.key) for e in events)


# --- features (streamed) --------------------------------------------------------------------

WINDOW_PRE_S = _kt.WINDOW_PRE_S
WINDOW_POST_S = _kt.WINDOW_POST_S


def session_features(
    sess: Session,
    samples: Sequence[int],
    pre_s: float = WINDOW_PRE_S,
    post_s: float = WINDOW_POST_S,
    n_sub: int = 2,
    block_rows: int = 1 << 18,
) -> np.ndarray:
    """:func:`fidetype.adapters.kt_semg.window_features` at the given sample rows, read in blocks.

    The session is read in blocks of ``block_rows`` rows plus a margin of
    one window, so memory stays at a few tens of MB for any file size.
    Returns ``(K, n_sub * 32)`` float64 in the order of ``samples``.
    """
    s = np.asarray(samples, dtype=np.int64)
    out = np.zeros((len(s), n_sub * N_CHANNELS), dtype=np.float64)
    if len(s) == 0:
        return out
    pad = int(math.ceil(max(pre_s, post_s) * SAMPLE_RATE_HZ)) + 2
    order = np.argsort(s, kind="stable")
    ss = s[order]
    for b in range(0, sess.n_samples, block_rows):
        sel = np.flatnonzero((ss >= b) & (ss < b + block_rows))
        if not len(sel):
            continue
        lo = max(b - pad, 0)
        emg = sess.read_emg(lo, min(b + block_rows + pad, sess.n_samples))
        t_local = (ss[sel] - lo) / SAMPLE_RATE_HZ
        out[order[sel]] = _kt.window_features(emg, t_local, SAMPLE_RATE_HZ, pre_s, post_s, n_sub)
    return out


# --- streams ------------------------------------------------------------------------------


def opaque_stream_id(*parts: Any) -> str:
    """Deterministic opaque ``stream.id``: SHA-256 of the parts, 32 hex characters."""
    return hashlib.sha256("/".join(str(p) for p in parts).encode()).hexdigest()[:32]


def session_stream_id(session_name: str, prompt_index: int, tag: str = "") -> str:
    """``stream.id`` of one prompt stream; the session name enters only through the hash."""
    return opaque_stream_id(DATASET_SLUG, session_name, prompt_index, tag)


def _licence_meta(licence: str) -> dict[str, Any]:
    """``data.licence`` and ``data.research_only`` of the dataset (FEP-0010, NTS 1.0 RC4 amendment 6)."""
    from fidetype.trust.licence import licence_meta

    return licence_meta(licence)


def stream_meta(
    session_index: int | None = None,
    prompt_index: int | None = None,
    decoder_name: str = "fidetype-emg2qwerty-lda-baseline",
    decoder_version: str = "0",
    weights_sha256: str | None = None,
    stream_id: str | None = None,
    personalized: bool = True,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """The ``meta`` of a prompt stream (spec 3.4 keys). No text, no user id, no session name."""
    replay: dict[str, Any] = {"dataset": DATASET_SLUG, "arxiv": ARXIV_ID, "licence": LICENCE,
                              "attribution": ATTRIBUTION, "research_only": True}
    if session_index is not None:
        replay["session_index"] = int(session_index)
    if prompt_index is not None:
        replay["prompt_index"] = int(prompt_index)
    m: dict[str, Any] = {
        "device.modality": "emg",
        "device.model": "two wristbands, 16 differential sEMG channels each, 2000 Hz (emg2qwerty)",
        "device.channel_count": N_CHANNELS,
        "device.invasive": False,
        "device.regulatory_status": "research",
        "emg.placement": "wrist",  # modality keys: NTS 1.0 RC4 MET-11 (FEP-0009)
        "emg.derivation": "bipolar",  # the dataset calls it differential
        "decoder.name": decoder_name,
        "decoder.version": decoder_version,
        "decoder.causal": False,
        "decoder.calibration_method": "none",
        "adapter.name": ADAPTER_NAME,
        "adapter.version": _FIDETYPE_VERSION,
        "lm.name": "none",
        "user.personalized": bool(personalized),
        "calibration.applied": False,
        "language": "en",
        "data.derived": True,
        **_licence_meta(LICENCE),  # data.licence, data.research_only: FEP-0010 (MET-12)
        "fidetype.vocab_id": KEY_VOCAB_ID,
        "fidetype.timing": "oracle-keystroke: one frame per key press; key-down times from the keylogger, on the "
                           "same unix clock as the EMG samples; seconds from the first EMG sample",
        "fidetype.replay": replay,
    }
    if weights_sha256 is not None:
        m["decoder.weights_sha256"] = weights_sha256
    if stream_id is not None:
        m["stream.id"] = stream_id
    if extra:
        m.update(extra)
    return m


def prompt_stream(
    log_probs: np.ndarray,
    key_times: Sequence[float],
    meta: dict[str, Any] | None = None,
    latency: float | None = None,
) -> NeuralTextStream:
    """One frame per key press over :data:`KEY_VOCAB` (see :func:`fidetype.adapters.kt_semg.keypress_stream`).

    With ``latency`` (the window time after the key press) the stream is
    causal with ``decoder.lookahead_s = latency``; without it
    ``decoder.causal = false``.
    """
    return _kt.keypress_stream(log_probs, key_times, meta if meta is not None else stream_meta(), latency=latency,
                               source=DATASET_SLUG)


greedy_codes = _kt.greedy_codes


# --- character-key CTC decoders -> track key codes (P11-09) ----------------------------------------
#
# A continuous decoder (for example P11-01) emits CTC tokens that are typed characters ("a", "A",
# "!", ...) plus Backspace / Enter marks. The emg2qwerty track scores the 32 KeyboardEvent.code classes
# of KEY_VOCAB. The writer below maps each token to its key code with the same rule as the track truth
# (key_code -> keep only codes in KEY_VOCAB): "a" and "A" -> KeyA; Backspace / Enter marks -> Backspace /
# Enter; digits, other symbols and modifiers -> no key (the truth drops them too).

#: Token spellings of Backspace and Enter in character-key CTC vocabularies (P11-01 uses these).
TOKEN_BACKSPACE = "⌫"
TOKEN_ENTER = "⏎"
_TOKEN_TYPED = {TOKEN_BACKSPACE: "\x08", TOKEN_ENTER: "\r", "\x08": "\x08", "\r": "\r", "\n": "\r"}
#: The guard sees Space as this character, so a key text is one token (no whitespace collapse).
KEY_SPACE_CHAR = "_"


def token_key_code(token: str) -> str | None:
    """The track key code (one of :data:`KEY_VOCAB`) of a character-key CTC token, or None (no key)."""
    ch = _TOKEN_TYPED.get(token, token)
    if len(ch) != 1:
        return None
    code = _kt.key_code(ch)
    return code if code in _CODE_INDEX else None


def key_chars() -> list[str]:
    """One character per :data:`KEY_VOCAB` class: the track text (``keycodes`` normaliser), Space as ``_``."""
    from fidetype.benchmark.registry import keycodes_to_chars

    ch = [keycodes_to_chars(c) for c in KEY_VOCAB]
    return [KEY_SPACE_CHAR if c == " " else c for c in ch]


def key_ctc_vocab() -> list[str]:
    """The vocabulary of :func:`merge_to_key_ctc`: ``<blank>`` then :func:`key_chars`."""
    return ["<blank>", *key_chars()]


def token_columns(vocab: Sequence[str], blank: int = 0) -> np.ndarray:
    """Target column of each vocabulary entry in the key CTC form: 0 = blank (blank and no-key tokens)."""
    cols = np.zeros(len(vocab), np.int64)
    for i, tok in enumerate(vocab):
        if i == blank:
            continue
        code = token_key_code(str(tok))
        cols[i] = 0 if code is None else 1 + _CODE_INDEX[code]
    return cols


def merge_to_key_ctc(log_probs: np.ndarray, vocab: Sequence[str], blank: int = 0) -> np.ndarray:
    """``(T, V)`` character-key CTC log-probs -> ``(T, 33)`` log-probs over :func:`key_ctc_vocab`.

    Each output column is the log-sum-exp of the input columns with that key code. Tokens with no key
    code join the blank: in the key space they emit nothing. Rows stay normalised. Known limit: two
    neighbour frames with different tokens of one key (``a`` then ``A``) collapse to one key press.
    """
    x = np.asarray(log_probs, np.float64)
    if x.ndim != 2 or x.shape[1] != len(vocab):
        raise ValueError(f"log_probs must be (T, {len(vocab)}), got {x.shape}")
    cols = token_columns(vocab, blank)
    out = np.full((x.shape[0], 1 + len(KEY_VOCAB)), -np.inf)
    for c in np.unique(cols):
        out[:, c] = np.logaddexp.reduce(x[:, cols == c], axis=1)
    return out.astype(np.float32)


def tokens_to_codes(tokens: str | Sequence[str]) -> str:
    """The writer: character-key CTC tokens (a string or a token list) -> ``"KeyH KeyI Space"``.

    Tokens with no key code are dropped, as in the track truth.
    """
    codes = (token_key_code(str(t)) for t in tokens)
    return " ".join(c for c in codes if c is not None)


def key_text_to_codes(text: str) -> str:
    """A key text over :func:`key_chars` (guard output) -> key codes. Other characters give ``?`` (unknown)."""
    inv = dict(zip(key_chars(), KEY_VOCAB))
    return " ".join(inv.get(c, "?") for c in text if not c.isspace())


def codes_to_key_text(codes: str) -> str:
    """Key codes -> a key text over :func:`key_chars` (the guard text of a truth)."""
    from fidetype.benchmark.registry import keycodes_to_chars

    return keycodes_to_chars(codes).replace(" ", KEY_SPACE_CHAR)


# --- baseline run ---------------------------------------------------------------------------


@dataclass
class SessionResult:
    """Aggregate-safe numbers of one session (no ids)."""

    n_events: int
    n_fit: int
    n_test: int
    correct: int
    majority_correct: int
    n_streams: int = 0
    n_frames: int = 0
    streams_at_level: int = 0


def _labelled(events: Sequence[KeyEvent]) -> tuple[np.ndarray, np.ndarray]:
    y = np.array([-1 if key_class(e.key) is None else key_class(e.key) for e in events], dtype=np.int64)
    return y, y >= 0


def run_session_baseline(
    sess: Session,
    session_index: int,
    out_dir: Path | None = None,
    min_frames: int = 3,
    level: str = "provenance",
    n_sub: int = 2,
    shrinkage: float = 0.1,
) -> SessionResult:
    """Session-calibrated baseline: fit the LDA on the first half of the key presses, replay the second half.

    Features are z-scored within the session (no labels). The test half
    becomes one stream per text prompt that starts after the split; each
    stream is checked at ``level`` and, with ``out_dir``, written as JSON
    Lines (``s<session>-p<prompt>.jsonl``, no names in the file name).
    """
    from fidetype.conformance import check_stream
    from fidetype.conformance.io import write_jsonl

    ev = key_events(sess, margin_s=WINDOW_PRE_S)
    X = _kt.standardize_run(session_features(sess, [e.sample for e in ev], n_sub=n_sub))
    y, ok = _labelled(ev)
    split = len(ev) // 2
    fit = np.flatnonzero(ok[:split])
    dec = _kt.LdaKeyDecoder.fit(X[fit], y[fit], shrinkage=shrinkage)
    sha = None
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        sha = dec.save(out_dir / f"s{session_index:03d}-lda.npz")
    else:
        sha = hashlib.sha256(dec.means.tobytes() + dec.precision.tobytes()).hexdigest()
    test = np.arange(split, len(ev))
    lp = dec.predict_log_proba(X[test]) if len(test) else np.zeros((0, len(KEY_VOCAB)))
    yt, okt = y[test], ok[test]
    majority = int(np.bincount(y[fit], minlength=len(KEY_VOCAB)).argmax())
    res = SessionResult(len(ev), len(fit), int(okt.sum()), int(np.sum(lp.argmax(1)[okt] == yt[okt])),
                        int(np.sum(yt[okt] == majority)))
    split_t = ev[split].t if split < len(ev) else math.inf
    pos = {id(e): i for i, e in enumerate(ev)}
    for pr in sess.prompts:
        pe = [e for e in prompt_events(sess, pr, ev) if e.t >= split_t]
        if len(pe) < min_frames:
            continue
        rows = np.array([pos[id(e)] - split for e in pe])
        meta = stream_meta(session_index, pr.index, weights_sha256=sha,
                           stream_id=session_stream_id(sess.name, pr.index, sha[:16]))
        s = prompt_stream(lp[rows], [e.t for e in pe], meta, latency=WINDOW_POST_S)
        rep = check_stream(s, f"s{session_index}/p{pr.index}", [pr.text, typed_text(pe)])
        res.n_streams += 1
        res.n_frames += s.n_frames
        res.streams_at_level += int(rep.passes(level))
        if out_dir is not None:
            write_jsonl(s, out_dir / f"s{session_index:03d}-p{pr.index:03d}.jsonl")
    return res


def run_cross_session(fit_sess: Session, test_sess: Session, n_sub: int = 2, shrinkage: float = 0.1) -> tuple[int, int, int]:
    """Same user, other day: fit on all key presses of one session, test on all of another.

    Returns (test key presses in the vocabulary, correct, majority-class correct).
    """
    out = []
    for s in (fit_sess, test_sess):
        ev = key_events(s, margin_s=WINDOW_PRE_S)
        X = _kt.standardize_run(session_features(s, [e.sample for e in ev], n_sub=n_sub))
        y, ok = _labelled(ev)
        out.append((X[ok], y[ok]))
    (Xf, yf), (Xt, yt) = out
    dec = _kt.LdaKeyDecoder.fit(Xf, yf, shrinkage=shrinkage)
    pred = dec.predict_log_proba(Xt).argmax(1)
    maj = int(np.bincount(yf, minlength=len(KEY_VOCAB)).argmax())
    return len(yt), int(np.sum(pred == yt)), int(np.sum(yt == maj))


def _rate(a: int, b: int) -> float | None:
    return round(a / b, 4) if b else None


def run_baseline(
    root: str | PathLike[str],
    n_users: int,
    sessions_per_user: int,
    out_dir: str | PathLike[str] | None = None,
    write_streams: bool = True,
    level: str = "provenance",
    cross_session: bool = True,
    progress: bool = True,
) -> dict[str, Any]:
    """The documented baseline on a subset (:func:`select_subset`). Returns an aggregate report only."""
    r = Path(root)
    subset = select_subset(read_metadata(r / "metadata.csv"), n_users, sessions_per_user)
    out = Path(out_dir) if out_dir is not None else None
    tot = SessionResult(0, 0, 0, 0, 0)
    per_session_acc: list[float] = []
    cross = [0, 0, 0]
    k = 0
    for sessions in subset:
        for name in sessions:
            with Session(r / f"{name}.hdf5") as s:
                res = run_session_baseline(s, k, out if (out is not None and write_streams) else None, level=level)
            for f in ("n_events", "n_fit", "n_test", "correct", "majority_correct", "n_streams", "n_frames",
                      "streams_at_level"):
                setattr(tot, f, getattr(tot, f) + getattr(res, f))
            if res.n_test:
                per_session_acc.append(res.correct / res.n_test)
            if progress:
                print(f"session {k}: {res.n_test} test keys, acc {_rate(res.correct, res.n_test)}", file=sys.stderr)
            k += 1
        if cross_session and len(sessions) >= 2:
            with Session(r / f"{sessions[0]}.hdf5") as a, Session(r / f"{sessions[1]}.hdf5") as b:
                n, c, m = run_cross_session(a, b)
            cross = [cross[0] + n, cross[1] + c, cross[2] + m]
    acc = np.array(per_session_acc)
    report: dict[str, Any] = {
        "dataset": DATASET_SLUG, "licence": LICENCE, "research_only": True, "adapter_version": _FIDETYPE_VERSION,
        "subset": {"rule": "users sorted by id; first n_users with >= sessions_per_user sessions; first sessions "
                           "in name order", "n_users": len(subset), "sessions_per_user": sessions_per_user,
                   "sessions": k},
        "decoder": {"name": "fidetype-emg2qwerty-lda-baseline", "features": "log-RMS, 32 channels x 2 sub-windows "
                    f"of [-{WINDOW_PRE_S}, +{WINDOW_POST_S}] s around key-down, z-scored per session",
                    "classes": len(KEY_VOCAB), "shrinkage": 0.1},
        "session_calibrated": {
            "key_presses": tot.n_events, "fit_in_vocab": tot.n_fit, "test_in_vocab": tot.n_test,
            "accuracy": _rate(tot.correct, tot.n_test), "majority_rate": _rate(tot.majority_correct, tot.n_test),
            "per_session_accuracy_min_median_max": [round(float(acc.min()), 4), round(float(np.median(acc)), 4),
                                                    round(float(acc.max()), 4)] if len(acc) else [],
            "streams": tot.n_streams, "frames": tot.n_frames, f"streams_at_{level}": tot.streams_at_level,
        },
    }
    if cross_session:
        report["cross_session_same_user"] = {"pairs": sum(1 for s in subset if len(s) >= 2), "test_in_vocab": cross[0],
                                             "accuracy": _rate(cross[1], cross[0]),
                                             "majority_rate": _rate(cross[2], cross[0])}
    if out is not None:
        out.mkdir(parents=True, exist_ok=True)
        (out / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


# --- CLI ------------------------------------------------------------------------------------


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m fidetype.adapters.emg2qwerty",
                                description="emg2qwerty (research use only, CC BY-NC-SA 4.0) -> NeuralTextStream "
                                            "replay streams.")
    sub = p.add_subparsers(dest="cmd", required=True)
    ps = sub.add_parser("summary", help="aggregate counts from metadata.csv (no per-user numbers)")
    ps.add_argument("root", help="folder with metadata.csv and the *.hdf5 sessions")
    pb = sub.add_parser("baseline", help="session-calibrated LDA baseline on a documented subset; aggregate report")
    pb.add_argument("root")
    pb.add_argument("--users", type=int, default=4)
    pb.add_argument("--sessions-per-user", type=int, default=2)
    pb.add_argument("--out", default=None, help="folder for report.json, weights and streams (outside the repo)")
    pb.add_argument("--no-streams", action="store_true", help="do not write stream files")
    pb.add_argument("--no-cross-session", action="store_true")
    pb.add_argument("--level", default="provenance", choices=("core", "trust-ready", "provenance"))
    a = p.parse_args(argv)
    if a.cmd == "summary":
        print(json.dumps(metadata_summary(read_metadata(Path(a.root) / "metadata.csv")), indent=2))
        return 0
    rep = run_baseline(a.root, a.users, a.sessions_per_user, a.out, write_streams=not a.no_streams, level=a.level,
                       cross_session=not a.no_cross_session)
    print(json.dumps(rep, indent=2))
    sc = rep["session_calibrated"]
    return 0 if sc[f"streams_at_{a.level}"] == sc["streams"] else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())


__all__ = [
    "KEY_VOCAB", "KEY_VOCAB_ID", "LICENCE", "Keystroke", "Prompt", "Session", "KeyEvent", "key_code", "key_class",
    "typed_char", "parse_keystrokes", "parse_prompts", "list_sessions", "read_metadata", "metadata_summary",
    "select_subset", "key_events", "prompt_events", "typed_text", "session_features", "stream_meta", "prompt_stream",
    "session_stream_id", "opaque_stream_id", "greedy_codes", "run_session_baseline", "run_cross_session",
    "run_baseline", "main", "TOKEN_BACKSPACE", "TOKEN_ENTER", "KEY_SPACE_CHAR", "token_key_code", "key_chars",
    "key_ctc_vocab", "token_columns", "merge_to_key_ctc", "tokens_to_codes", "key_text_to_codes",
    "codes_to_key_text",
]
